"""
Tests for warehouse.load_raw.

These build real bronze-layer Parquet files on a temp filesystem (shaped
exactly like extract_locations.py / extract_measurements.py would produce),
load them into a real (temp, throwaway) DuckDB file, and assert on the
actual SQL results -- not mocks. Loading logic is exactly the kind of thing
that looks right by inspection and is subtly wrong in practice (glob
patterns, partition columns, dedup boundaries), so it earns real tests.
"""

from __future__ import annotations

import pandas as pd
import pytest

from warehouse import load_raw
from warehouse.db import get_connection, init_db


@pytest.fixture
def bronze_dir(tmp_path, monkeypatch):
    """Build a fake bronze layer with two ingest_date partitions per source."""
    locations_p1 = tmp_path / "locations" / "ingest_date=2026-06-29"
    locations_p2 = tmp_path / "locations" / "ingest_date=2026-06-30"
    measurements_p1 = tmp_path / "measurements" / "ingest_date=2026-06-29"
    measurements_p2 = tmp_path / "measurements" / "ingest_date=2026-06-30"
    for p in (locations_p1, locations_p2, measurements_p1, measurements_p2):
        p.mkdir(parents=True)

    pd.DataFrame(
        [
            {"id": 1, "name": "Delhi", "country__code": "IN", "_ingested_iso": "IN"},
            {"id": 2, "name": "Mumbai", "country__code": "IN", "_ingested_iso": "IN"},
        ]
    ).to_parquet(locations_p1 / "locations.parquet", index=False)

    pd.DataFrame([{"id": 3, "name": "Berlin", "country__code": "DE", "_ingested_iso": "DE"}]).to_parquet(
        locations_p2 / "locations.parquet", index=False
    )

    pd.DataFrame(
        [
            {"sensor_id": 100, "location_id": 1, "value": 12.4, "parameter__name": "pm25"},
            {"sensor_id": 101, "location_id": 1, "value": 0.02, "parameter__name": "o3"},
        ]
    ).to_parquet(measurements_p1 / "measurements.parquet", index=False)

    pd.DataFrame([{"sensor_id": 200, "location_id": 3, "value": 8.1, "parameter__name": "pm25"}]).to_parquet(
        measurements_p2 / "measurements.parquet", index=False
    )

    # Patch load_raw's SOURCES to point at our temp bronze dir instead of the real one.
    monkeypatch.setattr(
        load_raw,
        "SOURCES",
        {
            "locations": tmp_path / "locations" / "ingest_date=*" / "locations.parquet",
            "measurements": tmp_path / "measurements" / "ingest_date=*" / "measurements.parquet",
        },
    )
    return tmp_path


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point warehouse.db at a throwaway DuckDB file for the duration of the test."""
    db_path = tmp_path / "test.duckdb"
    monkeypatch.setattr("warehouse.db.DB_PATH", db_path)
    yield db_path


def test_full_refresh_loads_all_partitions(bronze_dir, temp_db):
    results = load_raw.load_all(mode="full")

    assert results == {"locations": 3, "measurements": 3}

    conn = get_connection(read_only=True)
    locations = conn.execute("SELECT id, name FROM raw.locations ORDER BY id").fetchall()
    assert locations == [(1, "Delhi"), (2, "Mumbai"), (3, "Berlin")]
    conn.close()


def test_full_refresh_tags_each_row_with_source_file(bronze_dir, temp_db):
    load_raw.load_all(mode="full")
    conn = get_connection(read_only=True)
    source_files = conn.execute("SELECT DISTINCT _source_file FROM raw.locations").fetchall()
    conn.close()
    # Two partitions went in, so we should see two distinct source files,
    # each one pointing at the correct ingest_date directory.
    assert len(source_files) == 2
    assert any("ingest_date=2026-06-29" in f[0] for f in source_files)
    assert any("ingest_date=2026-06-30" in f[0] for f in source_files)


def test_full_refresh_is_idempotent(bronze_dir, temp_db):
    """Running full refresh twice in a row should produce the same row count, not double it."""
    load_raw.load_all(mode="full")
    results_second_run = load_raw.load_all(mode="full")
    assert results_second_run == {"locations": 3, "measurements": 3}


def test_init_db_creates_expected_schemas(temp_db):
    init_db()
    conn = get_connection(read_only=True)
    schemas = {
        row[0] for row in conn.execute("SELECT schema_name FROM information_schema.schemata").fetchall()
    }
    conn.close()
    assert {"raw", "staging", "mart"}.issubset(schemas)


def test_incremental_append_falls_back_to_full_refresh_when_table_missing(bronze_dir, temp_db):
    init_db()
    results = load_raw.load_all(mode="incremental")
    assert results == {"locations": 3, "measurements": 3}


def test_incremental_append_only_loads_new_partitions_when_table_exists(tmp_path, temp_db, monkeypatch):
    """
    Regression test for a real bug caught while building Phase 3: incremental_append()
    referenced a column (_ingest_date) that full_refresh() never actually created, so
    this code path raised "column does not exist" the moment a table already had data
    in it. The previous test only exercised the "table missing" fallback branch, which
    is exactly how this went uncaught -- so this test specifically forces the
    "table already exists" branch instead.
    """
    day1 = tmp_path / "locations" / "ingest_date=2026-06-29"
    day1.mkdir(parents=True)
    pd.DataFrame([{"id": 1, "name": "Delhi"}]).to_parquet(day1 / "locations.parquet", index=False)

    monkeypatch.setattr(
        load_raw,
        "SOURCES",
        {"locations": tmp_path / "locations" / "ingest_date=*" / "locations.parquet"},
    )

    first_results = load_raw.load_all(mode="incremental")
    assert first_results == {"locations": 1}

    # A second day's bronze partition lands...
    day2 = tmp_path / "locations" / "ingest_date=2026-06-30"
    day2.mkdir(parents=True)
    pd.DataFrame([{"id": 2, "name": "Mumbai"}]).to_parquet(day2 / "locations.parquet", index=False)

    # ...and this time raw.locations already exists, so we hit the real
    # incremental_append() branch, not the "table missing" fallback.
    second_results = load_raw.load_all(mode="incremental")
    assert second_results == {"locations": 2}

    conn = get_connection(read_only=True)
    rows = conn.execute("SELECT id, name FROM raw.locations ORDER BY id").fetchall()
    conn.close()
    assert rows == [(1, "Delhi"), (2, "Mumbai")]


def test_incremental_append_does_not_reload_same_partition_twice(tmp_path, temp_db, monkeypatch):
    """Running incremental append again with no new partitions must not duplicate rows."""
    day1 = tmp_path / "locations" / "ingest_date=2026-06-29"
    day1.mkdir(parents=True)
    pd.DataFrame([{"id": 1, "name": "Delhi"}]).to_parquet(day1 / "locations.parquet", index=False)
    monkeypatch.setattr(
        load_raw,
        "SOURCES",
        {"locations": tmp_path / "locations" / "ingest_date=*" / "locations.parquet"},
    )

    load_raw.load_all(mode="incremental")
    results = load_raw.load_all(mode="incremental")
    assert results == {"locations": 1}
