"""
Integration tests: run the actual extract_locations / extract_measurements
pipelines end-to-end against a mocked OpenAQClient and a real temp
filesystem, so we know the bronze-layer Parquet writes actually work --
not just that the client's pagination logic is correct in isolation.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pandas as pd

from ingestion import extract_locations, extract_measurements
from tests.test_schemas import LOCATION_EXAMPLE


def test_extract_locations_end_to_end_writes_valid_parquet(tmp_path):
    fake_client = object.__new__(extract_locations.OpenAQClient)  # bypass __init__/API key check

    with patch.object(
        extract_locations.OpenAQClient,
        "get_locations",
        return_value=iter([LOCATION_EXAMPLE]),
    ):
        records = extract_locations.fetch_locations(fake_client, iso_codes=["IN"])

    assert len(records) == 1
    assert records[0]["_ingested_iso"] == "IN"

    out_path = extract_locations.write_bronze(records, ingest_date=date(2026, 7, 1), bronze_dir=tmp_path)

    assert out_path.exists()
    df = pd.read_parquet(out_path)
    assert len(df) == 1
    assert df.iloc[0]["id"] == 8118
    assert (tmp_path / "locations" / "ingest_date=2026-07-01" / "raw.json").exists()


def test_extract_locations_limits_to_moderate_sensor_locations_per_country():
    fake_client = object.__new__(extract_locations.OpenAQClient)  # bypass __init__/API key check

    def location_fixture(location_id: int, iso: str, sensor_count: int) -> dict:
        sensors = []
        for sensor_idx in range(sensor_count):
            sensors.append(
                {
                    "id": location_id * 100 + sensor_idx,
                    "name": f"sensor-{sensor_idx}",
                    "parameter": {
                        "id": sensor_idx + 1,
                        "name": f"param{sensor_idx}",
                        "units": "µg/m³",
                        "displayName": f"Param {sensor_idx}",
                    },
                }
            )
        return {
            **LOCATION_EXAMPLE,
            "id": location_id,
            "name": f"{iso}-{location_id}",
            "country": {**LOCATION_EXAMPLE["country"], "code": iso, "name": iso},
            "sensors": sensors,
        }

    def fake_get_locations(self, iso, **kwargs):
        del self, kwargs
        sensor_counts = [1, 2, 3, 4, 5, 6, 7, 8, 25, 50, 75, 100]
        country_offset = 1000 if iso == "US" else 2000
        return iter(
            [
                location_fixture(
                    location_id=country_offset + sensor_count,
                    iso=iso,
                    sensor_count=sensor_count,
                )
                for sensor_count in sensor_counts
            ]
        )

    with patch.object(extract_locations.OpenAQClient, "get_locations", fake_get_locations):
        records = extract_locations.fetch_locations(
            fake_client,
            iso_codes=["US", "IN"],
            limit_locations_per_country=5,
        )

    assert len(records) == 10
    assert {record["_ingested_iso"] for record in records} == {"US", "IN"}
    assert max(len(record["sensors"]) for record in records) == 8
    assert {len(record["sensors"]) for record in records if record["_ingested_iso"] == "US"} == set(
        range(4, 9)
    )
    assert {len(record["sensors"]) for record in records if record["_ingested_iso"] == "IN"} == set(
        range(4, 9)
    )


def test_extract_locations_can_prioritize_major_indian_cities_with_country_limit():
    fake_client = object.__new__(extract_locations.OpenAQClient)  # bypass __init__/API key check

    def location_fixture(location_id: int, iso: str, name: str) -> dict:
        return {
            **LOCATION_EXAMPLE,
            "id": location_id,
            "name": name,
            "locality": name,
            "country": {**LOCATION_EXAMPLE["country"], "code": iso, "name": iso},
        }

    def fake_get_locations(self, iso, **kwargs):
        del self, kwargs
        if iso == "IN":
            names = ["Nagpur", "New Delhi", "Mumbai", "Kolkata", "Jaipur"]
        else:
            names = ["Boston", "Seattle", "Chicago"]
        return iter(
            [location_fixture(location_id=index + 1, iso=iso, name=name) for index, name in enumerate(names)]
        )

    with patch.object(extract_locations.OpenAQClient, "get_locations", fake_get_locations):
        records = extract_locations.fetch_locations(
            fake_client,
            iso_codes=["US", "IN"],
            limit_locations_per_country=2,
            country_location_limits={"IN": 3},
        )

    india_names = {record["name"] for record in records if record["_ingested_iso"] == "IN"}
    us_names = {record["name"] for record in records if record["_ingested_iso"] == "US"}

    assert len(us_names) == 2
    assert india_names == {"New Delhi", "Mumbai", "Kolkata"}


def test_extract_locations_prefers_recent_activity_before_major_city_priority():
    stale_mumbai = {
        **LOCATION_EXAMPLE,
        "id": 1,
        "name": "Mumbai stale station",
        "locality": "Mumbai",
        "datetimeLast": {"utc": "2024-01-01T00:00:00Z", "local": "2024-01-01T05:30:00+05:30"},
    }
    recent_station = {
        **LOCATION_EXAMPLE,
        "id": 2,
        "name": "Recently Active Station",
        "locality": "India",
        "datetimeLast": {"utc": "2026-07-01T00:00:00Z", "local": "2026-07-01T05:30:00+05:30"},
    }

    selected = sorted(
        [stale_mumbai, recent_station],
        key=lambda location: extract_locations.location_importance_key(location, "IN"),
        reverse=True,
    )

    assert selected[0]["name"] == "Recently Active Station"


def test_extract_measurements_end_to_end_reads_locations_and_writes_parquet(tmp_path):
    # Step 1: seed a fake locations snapshot, exactly like extract_locations would.
    locations_records = [{**LOCATION_EXAMPLE, "_ingested_iso": "IN"}]
    extract_locations.write_bronze(locations_records, ingest_date=date(2026, 7, 1), bronze_dir=tmp_path)

    # Step 2: point extract_measurements at that snapshot and mock the sensor pull.
    locations_path = extract_measurements.latest_locations_snapshot(bronze_dir=tmp_path)
    sensors = extract_measurements.sensor_ids_from_locations(locations_path)

    assert sensors == [
        {
            "sensor_id": 23534,
            "location_id": 8118,
            "location_name": "New Delhi",
            "parameter_name": "pm25",
        }
    ]

    fake_hourly_record = {
        "value": 12.4,
        "flagInfo": {"hasFlags": False},
        "parameter": {"id": 2, "name": "pm25", "units": "\u00b5g/m\u00b3", "displayName": "PM2.5"},
        "period": {"datetimeFrom": {"utc": "2026-06-29T00:00:00Z", "local": "2026-06-29T00:00:00Z"}},
    }
    fake_client = object.__new__(extract_measurements.OpenAQClient)
    with patch.object(
        extract_measurements.OpenAQClient,
        "get_hourly_measurements",
        return_value=iter([fake_hourly_record]),
    ):
        measurements = extract_measurements.fetch_measurements(fake_client, sensors, lookback_days=3)

    assert len(measurements) == 1
    assert measurements[0]["sensor_id"] == 23534
    assert measurements[0]["value"] == 12.4

    out_path = extract_measurements.write_bronze(
        measurements, ingest_date=date(2026, 7, 1), bronze_dir=tmp_path
    )
    df = pd.read_parquet(out_path)
    assert len(df) == 1
    assert df.iloc[0]["sensor_id"] == 23534


def test_extract_measurements_caps_sensors_per_location_with_pollutant_diversity(tmp_path):
    def sensor(sensor_id: int, parameter_name: str) -> dict:
        return {
            "id": sensor_id,
            "name": f"{parameter_name}-{sensor_id}",
            "parameter": {
                "id": sensor_id,
                "name": parameter_name,
                "units": "µg/m³",
                "displayName": parameter_name.upper(),
            },
        }

    locations_records = [
        {
            **LOCATION_EXAMPLE,
            "_ingested_iso": "IN",
            "sensors": [
                sensor(1, "co"),
                sensor(2, "co"),
                sensor(3, "pm25"),
                sensor(4, "pm10"),
                sensor(5, "no2"),
                sensor(6, "o3"),
            ],
        }
    ]
    extract_locations.write_bronze(locations_records, ingest_date=date(2026, 7, 1), bronze_dir=tmp_path)

    locations_path = extract_measurements.latest_locations_snapshot(bronze_dir=tmp_path)
    sensors = extract_measurements.sensor_ids_from_locations(
        locations_path,
        max_sensors_per_location=4,
    )

    assert [sensor["parameter_name"] for sensor in sensors] == ["pm25", "pm10", "no2", "o3"]


def test_extract_measurements_builds_location_availability_report():
    sensors = [
        {"sensor_id": 1, "location_id": 100, "location_name": "Delhi", "parameter_name": "pm25"},
        {"sensor_id": 2, "location_id": 100, "location_name": "Delhi", "parameter_name": "pm10"},
        {"sensor_id": 3, "location_id": 200, "location_name": "Mumbai", "parameter_name": "no2"},
    ]
    sensor_statuses = {
        1: {"hourly_records": 24, "failed": False},
        2: {"hourly_records": 0, "failed": False},
        3: {"hourly_records": 0, "failed": True},
    }

    report = extract_measurements.build_data_availability_report(sensors, sensor_statuses)

    assert report == [
        {
            "location_id": 100,
            "location_name": "Delhi",
            "sensors_checked": 2,
            "sensors_with_data": 1,
            "failed_sensors": 0,
            "hourly_records": 24,
            "pollutants_checked": ["pm25", "pm10"],
            "pollutants_with_data": ["pm25"],
        },
        {
            "location_id": 200,
            "location_name": "Mumbai",
            "sensors_checked": 1,
            "sensors_with_data": 0,
            "failed_sensors": 1,
            "hourly_records": 0,
            "pollutants_checked": ["no2"],
            "pollutants_with_data": [],
        },
    ]


def test_extract_measurements_one_bad_sensor_does_not_kill_the_run(tmp_path):
    """A single sensor erroring out should be logged and skipped, not crash the batch."""
    sensors = [
        {"sensor_id": 1, "location_id": 100, "location_name": "A", "parameter_name": "pm25"},
        {"sensor_id": 2, "location_id": 100, "location_name": "A", "parameter_name": "o3"},
    ]

    def flaky_get_hourly_measurements(self, sensor_id, **kwargs):
        if sensor_id == 1:
            raise RuntimeError("simulated transient failure")
        yield {
            "value": 5.0,
            "flagInfo": {"hasFlags": False},
            "parameter": {"id": 3, "name": "o3", "units": "ppm", "displayName": "O3"},
            "period": {"datetimeFrom": {"utc": "2026-06-29T00:00:00Z", "local": "2026-06-29T00:00:00Z"}},
        }

    fake_client = object.__new__(extract_measurements.OpenAQClient)
    with patch.object(
        extract_measurements.OpenAQClient, "get_hourly_measurements", flaky_get_hourly_measurements
    ):
        measurements = extract_measurements.fetch_measurements(fake_client, sensors, lookback_days=3)

    # sensor 1 failed and was skipped; sensor 2 still made it through
    assert len(measurements) == 1
    assert measurements[0]["sensor_id"] == 2
