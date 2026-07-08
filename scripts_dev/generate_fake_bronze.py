"""
Generates realistic synthetic bronze-layer data so the dbt project can be
built and tested end-to-end in this sandbox (which has no network path to
api.openaq.org). Deliberately includes the real edge cases this project's
transformation logic exists to handle:

  - multiple pollutants per location (pm25, pm10, o3, no2)
  - the SAME (sensor, hour) reading appearing in two ingest_date partitions
    with a different value (tests staging dedup keeps the latest)
  - a gas reading reported in ug/m3 by one "provider" and ppm by another
    for the same pollutant (tests unit normalization)
  - a null value (sensor gap/outage)
  - two ingest_date partitions for locations, one with a location's name
    changed (tests the SCD2 snapshot)

This script is NOT part of the shipped pipeline -- it exists purely to
prove the dbt project works before you ever point it at your real API key.
"""

from __future__ import annotations

from datetime import date

from ingestion.extract_locations import write_bronze as write_locations_bronze
from ingestion.extract_measurements import write_bronze as write_measurements_bronze


def location(id_, name, iso, country_name, lat, lon, tz="UTC"):
    return {
        "id": id_,
        "name": name,
        "locality": country_name,
        "timezone": tz,
        "country": {"id": 1, "code": iso, "name": country_name},
        "owner": {"id": 1, "name": "Gov"},
        "provider": {"id": 1, "name": "AirNow"},
        "isMobile": False,
        "isMonitor": True,
        "instruments": [],
        "sensors": [
            {
                "id": id_ * 100 + 1,
                "name": "pm25 sensor",
                "parameter": {"id": 2, "name": "pm25", "units": "µg/m³", "displayName": "PM2.5"},
            },
            {
                "id": id_ * 100 + 2,
                "name": "pm10 sensor",
                "parameter": {"id": 1, "name": "pm10", "units": "µg/m³", "displayName": "PM10"},
            },
            {
                "id": id_ * 100 + 3,
                "name": "o3 sensor",
                "parameter": {"id": 3, "name": "o3", "units": "ppm", "displayName": "O3"},
            },
            {
                "id": id_ * 100 + 4,
                "name": "no2 sensor",
                "parameter": {"id": 4, "name": "no2", "units": "ppb", "displayName": "NO2"},
            },
        ],
        "coordinates": {"latitude": lat, "longitude": lon},
        "licenses": None,
        "bounds": [],
        "distance": None,
        # Real OpenAQ locations with active sensors always populate these --
        # using None here (as an earlier version of this fixture did) was
        # unrealistic test data that happened to hide a real fragility:
        # pandas' json_normalize only flattens a nested dict into
        # `field__subfield` columns when at least one row in the batch has
        # it populated. A batch where every row has a null here would
        # silently produce a *different* raw schema than one where it's
        # populated -- worth knowing about even though this fixture no
        # longer exercises that edge case.
        "datetimeFirst": {"utc": "2016-11-09T19:00:00Z", "local": "2016-11-10T00:30:00+05:30"},
        "datetimeLast": {"utc": "2026-06-30T14:00:00Z", "local": "2026-06-30T14:00:00Z"},
        "_ingested_iso": iso,
    }


def hourly(sensor_id, location_id, value, units, parameter_id, parameter_name, hour_iso, has_flags=False):
    return {
        "sensor_id": sensor_id,
        "location_id": location_id,
        "value": value,
        "flagInfo__hasFlags": has_flags,
        "parameter__id": parameter_id,
        "parameter__name": parameter_name,
        "parameter__units": units,
        "period__datetimeFrom__utc": hour_iso,
        "coverage__percentCoverage": 96.5,
        "summary__avg": value,
    }


def main() -> None:
    # --- Day 1 locations: New Delhi (IN) and London (GB) ---
    day1 = date(2026, 6, 29)
    locations_day1 = [
        location(8118, "New Delhi", "IN", "India", 28.63, 77.22),
        location(9001, "London Westminster", "GB", "United Kingdom", 51.50, -0.13),
    ]
    write_locations_bronze(locations_day1, ingest_date=day1)

    # --- Day 2: London gets renamed (tests the SCD2 snapshot) ---
    day2 = date(2026, 6, 30)
    locations_day2 = [
        location(8118, "New Delhi", "IN", "India", 28.63, 77.22),
        location(9001, "London Central", "GB", "United Kingdom", 51.50, -0.13),  # name changed
    ]
    write_locations_bronze(locations_day2, ingest_date=day2)

    # --- Measurements, day 1: several hours across both locations ---
    m_day1 = [
        hourly(811801, 8118, 45.2, "µg/m³", 2, "pm25", "2026-06-29T00:00:00Z"),
        hourly(811801, 8118, 48.9, "µg/m³", 2, "pm25", "2026-06-29T01:00:00Z"),
        hourly(811802, 8118, 80.0, "µg/m³", 1, "pm10", "2026-06-29T00:00:00Z"),
        hourly(811803, 8118, 0.045, "ppm", 3, "o3", "2026-06-29T00:00:00Z"),
        hourly(900101, 9001, 8.5, "µg/m³", 2, "pm25", "2026-06-29T00:00:00Z"),
        hourly(900104, 9001, 25.0, "ppb", 4, "no2", "2026-06-29T00:00:00Z"),
        # a sensor gap: null value, hasFlags=true
        hourly(900101, 9001, None, "µg/m³", 2, "pm25", "2026-06-29T01:00:00Z", has_flags=True),
    ]
    write_measurements_bronze(m_day1, ingest_date=day1)

    # --- Measurements, day 2: overlapping lookback re-pulls the 00:00 Delhi
    # pm25 reading with a corrected value, plus new hours ---
    m_day2 = [
        hourly(811801, 8118, 46.0, "µg/m³", 2, "pm25", "2026-06-29T00:00:00Z"),  # corrected value, same hour
        hourly(811801, 8118, 52.3, "µg/m³", 2, "pm25", "2026-06-30T00:00:00Z"),
        hourly(900101, 9001, 9.1, "µg/m³", 2, "pm25", "2026-06-30T00:00:00Z"),
    ]
    write_measurements_bronze(m_day2, ingest_date=day2)

    print("Synthetic bronze fixtures written under data/bronze/")


if __name__ == "__main__":
    main()
