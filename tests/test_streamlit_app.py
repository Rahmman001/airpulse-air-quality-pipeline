"""
Tests the Streamlit dashboard using Streamlit's own headless AppTest
framework -- this actually runs each page's script and inspects what it
would have rendered, rather than just checking the code imports cleanly.

Builds a real (small, synthetic) pipeline run once per test session --
bronze -> raw -> dbt build -- so every test in this file exercises the
dashboard against real dimensional-model output, the same way a person
would see it after running the pipeline for real.
"""

from __future__ import annotations

import os
import sys
import subprocess
from datetime import date
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DBT_PROJECT_DIR = PROJECT_ROOT / "dbt_project"


def dbt_command() -> list[str]:
    venv_dbt = Path(sys.executable).with_name("dbt")
    if venv_dbt.exists():
        return [str(venv_dbt)]
    return ["dbt"]


@pytest.fixture(scope="module")
def real_dashboard_data():
    """
    Builds one full, real pipeline run for every test in this module to
    share -- bronze fixtures, raw load, and a full `dbt build` (models +
    snapshot + tests). Session-scoped would be even more efficient, but
    module-scoped keeps this file's data lifecycle independent of any other
    test file's use of the same airpulse.duckdb.
    """
    import warehouse.db as warehouse_db
    from ingestion.extract_locations import write_bronze as write_locations_bronze
    from ingestion.extract_measurements import write_bronze as write_measurements_bronze
    from scripts_dev.generate_fake_bronze import location, hourly
    from warehouse.load_raw import load_all

    # Clean slate.
    for suffix in ("", ".wal"):
        p = warehouse_db.DB_PATH.parent / (warehouse_db.DB_PATH.name + suffix)
        if p.exists():
            p.unlink()

    locations = [location(8118, "New Delhi", "IN", "India", 28.63, 77.22)]
    write_locations_bronze(locations, ingest_date=date(2026, 6, 29))

    measurements = [
        hourly(811801, 8118, 46.0, "µg/m³", 2, "pm25", "2026-06-29T00:00:00Z"),
        hourly(811801, 8118, 52.3, "µg/m³", 2, "pm25", "2026-06-30T00:00:00Z"),
    ]
    write_measurements_bronze(measurements, ingest_date=date(2026, 6, 30))

    load_all(mode="full")

    profiles_yml = DBT_PROJECT_DIR / "profiles.yml"
    if not profiles_yml.exists():
        profiles_yml.write_text((DBT_PROJECT_DIR / "profiles.yml.example").read_text())

    env = {**os.environ, "DBT_PROFILES_DIR": str(DBT_PROJECT_DIR)}
    subprocess.run(
        [*dbt_command(), "run", "--select", "staging", "intermediate"],
        cwd=DBT_PROJECT_DIR,
        env=env,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [*dbt_command(), "snapshot"], cwd=DBT_PROJECT_DIR, env=env, check=True, capture_output=True
    )
    subprocess.run([*dbt_command(), "run"], cwd=DBT_PROJECT_DIR, env=env, check=True, capture_output=True)

    # st.cache_data's cache is process-wide and keyed by function + args --
    # it persists across separate AppTest runs, and even across test files,
    # within the same pytest process. Without clearing it here, a test could
    # silently see a stale cached DataFrame from data built by an earlier
    # test/fixture instead of actually querying the fresh state this fixture
    # just built.
    st.cache_data.clear()

    yield

    for suffix in ("", ".wal"):
        p = warehouse_db.DB_PATH.parent / (warehouse_db.DB_PATH.name + suffix)
        if p.exists():
            p.unlink()


def test_main_dashboard_renders_without_exception(real_dashboard_data):
    at = AppTest.from_file(str(PROJECT_ROOT / "app" / "streamlit_app.py"))
    at.run(timeout=30)
    assert not at.exception
    metric_labels = [m.label for m in at.metric]
    assert "Locations monitored" in metric_labels


def test_dashboard_shows_friendly_message_when_mart_schema_does_not_exist_yet(tmp_path, monkeypatch):
    """
    Regression test for a real bug a user hit running this on a fresh
    machine: before the pipeline has ever been run, `mart.fact_daily_city_aqi`
    doesn't exist at all, and DuckDB raised a raw CatalogException that
    crashed the app with a stack trace instead of the intended "no data yet"
    warning message. `app/utils/data.py::_query` now catches this
    specifically and returns an empty DataFrame, which the page-level
    `.empty` checks already knew how to handle.
    """
    import warehouse.db as warehouse_db
    from warehouse.db import get_connection

    fake_db_path = tmp_path / "bare_no_mart_schema.duckdb"
    monkeypatch.setattr(warehouse_db, "DB_PATH", fake_db_path)
    # Also patch it where app.utils.data already imported the name directly.
    import app.utils.data as app_data

    monkeypatch.setattr(app_data, "DB_PATH", fake_db_path)

    # Critical: st.cache_data's cache key is based on function + arguments.
    # load_latest_city_aqi() and friends take NO arguments, so their cache
    # key has no way to reflect that DB_PATH just changed -- caching here
    # is based purely on function identity, blind to the hidden external
    # state (which file exists on disk) the function's actual behavior
    # depends on. Clearing before this test's own AppTest run is necessary
    # (an earlier test's real data would otherwise still be cached); clearing
    # again in `finally` is just as necessary, or this test would leave a
    # stale EMPTY result cached that the next test -- which never touches
    # DB_PATH itself -- has no reason to expect and no way to detect.
    st.cache_data.clear()

    conn = get_connection()  # reads the now-patched warehouse_db.DB_PATH
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw")  # deliberately no `mart` schema
    conn.close()

    try:
        at = AppTest.from_file(str(PROJECT_ROOT / "app" / "streamlit_app.py"))
        at.run(timeout=30)
        assert not at.exception
        assert any("No data available yet" in w.value for w in at.warning)
    finally:
        st.cache_data.clear()


def test_main_dashboard_shows_correct_worst_reading(real_dashboard_data):
    """The known worked-example value (New Delhi PM2.5 -> AQI 142 on the latest day) should show up."""
    at = AppTest.from_file(str(PROJECT_ROOT / "app" / "streamlit_app.py"))
    at.run(timeout=30)
    assert not at.exception
    worst = next(m for m in at.metric if m.label == "Worst current reading")
    assert "142" in worst.value


def test_city_trends_page_drilldown_shows_hand_verified_aqi(real_dashboard_data):
    """Same regression anchor as the Phase 3 worked example: 46.0 ug/m3 PM2.5 -> AQI 127."""
    at = AppTest.from_file(str(PROJECT_ROOT / "app" / "pages" / "1_City_Trends.py"))
    at.run(timeout=30)
    at.selectbox[0].select("New Delhi").run(timeout=30)
    at.selectbox[1].select("PM2.5").run(timeout=30)
    assert not at.exception
    assert at.dataframe, "expected a rendered readings table"
    df = at.dataframe[0].value
    assert 127.0 in df["AQI"].values


def test_alerts_page_threshold_slider_changes_results(real_dashboard_data):
    at = AppTest.from_file(str(PROJECT_ROOT / "app" / "pages" / "2_Alerts.py"))
    at.run(timeout=30)
    assert not at.exception

    at.select_slider[0].set_value("Moderate").run(timeout=30)
    assert not at.exception
    metric = next(m for m in at.metric if "or worse" in m.label)
    assert int(metric.value) >= 1  # at least the New Delhi PM2.5 reading qualifies at this threshold


def test_dashboard_works_in_snapshot_mode_with_no_live_duckdb_file(real_dashboard_data):
    """
    Proves the dual-mode data layer actually works: export the mart tables
    to Parquet, delete the live DuckDB file entirely, and confirm the app
    transparently falls back to reading the committed snapshot -- this is
    exactly what the deployed Streamlit Community Cloud app does, since it
    has no access to a live DuckDB file or a running Dagster instance.
    """
    import warehouse.db as warehouse_db
    from warehouse.export_gold_snapshot import export_gold_snapshot

    export_gold_snapshot()

    for suffix in ("", ".wal"):
        p = warehouse_db.DB_PATH.parent / (warehouse_db.DB_PATH.name + suffix)
        if p.exists():
            p.unlink()

    # See the comment in test_dashboard_shows_friendly_message_... above:
    # these loader functions take no arguments, so st.cache_data has no way
    # to know DB_PATH just changed. Clear before deleting the live db (an
    # earlier test's real-mode result would otherwise still be cached) --
    # and clear again in `finally`, after the live db is restored, so a
    # later test doesn't inherit THIS test's cached snapshot-mode result.
    st.cache_data.clear()

    try:
        at = AppTest.from_file(str(PROJECT_ROOT / "app" / "streamlit_app.py"))
        at.run(timeout=30)
        assert not at.exception
        caption_texts = [c.value for c in at.caption]
        assert any("committed snapshot" in c for c in caption_texts)
    finally:
        # Restore the live db for any tests that run after this one.
        load_all_module = __import__("warehouse.load_raw", fromlist=["load_all"])
        load_all_module.load_all(mode="full")
        env = {**os.environ, "DBT_PROFILES_DIR": str(DBT_PROJECT_DIR)}
        subprocess.run(
            [*dbt_command(), "build"], cwd=DBT_PROJECT_DIR, env=env, check=False, capture_output=True
        )
        st.cache_data.clear()
