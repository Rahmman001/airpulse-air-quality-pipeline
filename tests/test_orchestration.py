"""
Materializes the ENTIRE Dagster asset graph -- ingestion assets, the raw
DuckDB load, and every dbt model/snapshot -- in one shot, against mocked
OpenAQ API responses. This is the closest thing to "does the orchestrated
pipeline actually work end to end" that's possible without a live API key,
and it's a meaningfully different test than anything in tests/test_*.py:
those test each layer in isolation, while this proves Dagster actually
sequences all of them correctly together, including running `dbt build`
(which is what makes the SCD2 snapshot execute automatically, without the
manual `dbt run -> dbt snapshot -> dbt run` sequence Phase 3 required).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from dagster import DagsterInstance, materialize

from ingestion.openaq_client import OpenAQClient

LOCATION_FIXTURE = {
    "id": 8118,
    "name": "New Delhi",
    "locality": "India",
    "timezone": "Asia/Kolkata",
    "country": {"id": 9, "code": "IN", "name": "India"},
    "owner": {"id": 4, "name": "Gov"},
    "provider": {"id": 119, "name": "AirNow"},
    "isMobile": False,
    "isMonitor": True,
    "instruments": [],
    "sensors": [
        {
            "id": 811801,
            "name": "pm25 sensor",
            "parameter": {"id": 2, "name": "pm25", "units": "µg/m³", "displayName": "PM2.5"},
        },
    ],
    "coordinates": {"latitude": 28.63, "longitude": 77.22},
    "licenses": None,
    "bounds": [],
    "distance": None,
    "datetimeFirst": {"utc": "2016-11-09T19:00:00Z", "local": "2016-11-10T00:30:00+05:30"},
    "datetimeLast": {"utc": "2026-06-30T14:00:00Z", "local": "2026-06-30T14:00:00Z"},
}

MEASUREMENT_FIXTURE = {
    "value": 46.0,
    "flagInfo": {"hasFlags": False},
    "parameter": {"id": 2, "name": "pm25", "units": "µg/m³", "displayName": "PM2.5"},
    "period": {
        "label": "1hour",
        "interval": "01:00:00",
        "datetimeFrom": {"utc": "2026-06-29T00:00:00Z", "local": "2026-06-29T05:30:00+05:30"},
        "datetimeTo": {"utc": "2026-06-29T01:00:00Z", "local": "2026-06-29T06:30:00+05:30"},
    },
}


@pytest.fixture(autouse=True)
def fake_api_key(monkeypatch):
    monkeypatch.setenv("OPENAQ_API_KEY", "test-key-not-a-real-secret")


@pytest.fixture
def clean_bronze_and_db(tmp_path, monkeypatch):
    """
    Isolate the bronze directory to a temp path (Python-only, safe to fake).

    Deliberately does NOT redirect the DuckDB file to a temp path: dbt's
    profiles.yml hardcodes a path to the project's real airpulse.duckdb
    (dbt has no way to know about a path only warehouse/db.py's DB_PATH
    constant was told about), so faking that constant here would only
    isolate the Python side while dbt silently kept reading/writing the
    real file -- a misleading false sense of test isolation. Instead this
    resets the real project's airpulse.duckdb before and after the test,
    which is honest about the actual constraint: Python and dbt currently
    agree on where the warehouse lives by convention, not configuration.
    """
    import ingestion.config as ingestion_config
    import warehouse.db as warehouse_db
    import warehouse.load_raw as load_raw

    monkeypatch.setattr(ingestion_config, "BRONZE_DIR", tmp_path / "bronze")
    monkeypatch.setattr(
        load_raw,
        "SOURCES",
        {
            "locations": tmp_path / "bronze" / "locations" / "ingest_date=*" / "locations.parquet",
            "measurements": tmp_path / "bronze" / "measurements" / "ingest_date=*" / "measurements.parquet",
        },
    )

    real_db_path = warehouse_db.DB_PATH
    for suffix in ("", ".wal"):
        p = real_db_path.parent / (real_db_path.name + suffix)
        if p.exists():
            p.unlink()

    yield tmp_path

    for suffix in ("", ".wal"):
        p = real_db_path.parent / (real_db_path.name + suffix)
        if p.exists():
            p.unlink()


def test_full_asset_graph_materializes_end_to_end(clean_bronze_and_db):
    from orchestration.assets.dbt_assets import airpulse_dbt_assets
    from orchestration.assets.ingestion_assets import raw_locations, raw_measurements, raw_schema_loaded
    from orchestration.project import dbt_resource

    with patch.object(OpenAQClient, "get_locations", return_value=iter([LOCATION_FIXTURE])), patch.object(
        OpenAQClient, "get_hourly_measurements", return_value=iter([MEASUREMENT_FIXTURE])
    ):
        result = materialize(
            [raw_locations, raw_measurements, raw_schema_loaded, airpulse_dbt_assets],
            resources={"dbt": dbt_resource},
            instance=DagsterInstance.ephemeral(),
        )

    assert result.success

    # Prove data actually flowed all the way through to the marts, not just
    # that Dagster reported success.
    from warehouse.db import get_connection

    conn = get_connection(read_only=True)
    try:
        row = conn.execute(
            """
            SELECT l.location_name, p.parameter_name, f.aqi, f.risk_tier
            FROM mart.fact_air_quality_hourly f
            JOIN mart.dim_location l ON f.location_key = l.location_key
            JOIN mart.dim_pollutant p ON f.pollutant_key = p.pollutant_key
            """
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    location_name, parameter_name, aqi, risk_tier = row
    assert location_name == "New Delhi"
    assert parameter_name == "pm25"
    assert aqi == 127  # same hand-verified value as the Phase 3 worked example
    assert risk_tier == "Unhealthy for Sensitive Groups"
