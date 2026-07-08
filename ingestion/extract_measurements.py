"""
Phase 1 ingestion: pull hourly measurements for every sensor at every
previously-extracted location, and land them to the bronze layer.

Depends on extract_locations.py having been run at least once -- this script
reads the most recent bronze locations snapshot to know which sensor IDs to
pull measurements for.

Run:
    python -m ingestion.extract_measurements
    python -m ingestion.extract_measurements --lookback-days 7 --limit-sensors 25
    python -m ingestion.extract_measurements --max-sensors-per-location 5
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from ingestion.config import BRONZE_DIR, MEASUREMENT_LOOKBACK_DAYS
from ingestion.openaq_client import OpenAQClient
from ingestion.schemas import HourlyData

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PREFERRED_PARAMETER_ORDER = ["pm25", "pm10", "no2", "o3", "so2", "co"]
PREFERRED_PARAMETER_RANK = {parameter: rank for rank, parameter in enumerate(PREFERRED_PARAMETER_ORDER)}


def latest_locations_snapshot(bronze_dir: Path = BRONZE_DIR) -> Path:
    locations_root = bronze_dir / "locations"
    snapshots = sorted(locations_root.glob("ingest_date=*"))
    if not snapshots:
        raise FileNotFoundError(
            "No locations snapshot found. Run `python -m ingestion.extract_locations` first."
        )
    return snapshots[-1] / "locations.parquet"


def sensor_priority_key(sensor: dict) -> tuple[int, str, int]:
    parameter_name = sensor.get("parameter", {}).get("name") or ""
    return (
        PREFERRED_PARAMETER_RANK.get(parameter_name, len(PREFERRED_PARAMETER_RANK)),
        parameter_name,
        sensor.get("id", 0),
    )


def select_sensors_for_location(sensors: list[dict], max_sensors: Optional[int] = None) -> list[dict]:
    if max_sensors is None or len(sensors) <= max_sensors:
        return sorted(sensors, key=sensor_priority_key)

    selected: list[dict] = []
    seen_parameters: set[str] = set()
    for sensor in sorted(sensors, key=sensor_priority_key):
        parameter_name = sensor.get("parameter", {}).get("name") or ""
        if parameter_name in seen_parameters:
            continue
        selected.append(sensor)
        seen_parameters.add(parameter_name)
        if len(selected) == max_sensors:
            return selected

    for sensor in sorted(sensors, key=sensor_priority_key):
        if sensor in selected:
            continue
        selected.append(sensor)
        if len(selected) == max_sensors:
            return selected

    return selected


def sensor_ids_from_locations(
    locations_path: Path, max_sensors_per_location: Optional[int] = None
) -> list[dict]:
    """Flatten the nested `sensors` array out of the locations snapshot."""
    df = pd.read_parquet(locations_path)
    sensor_rows = []
    for _, row in df.iterrows():
        sensors = row.get("sensors")
        if sensors is None:
            continue
        for sensor in select_sensors_for_location(sensors, max_sensors=max_sensors_per_location):
            sensor_rows.append(
                {
                    "sensor_id": sensor["id"],
                    "location_id": row["id"],
                    "location_name": row.get("name"),
                    "parameter_name": sensor["parameter"]["name"],
                }
            )
    return sensor_rows


def fetch_measurements(client: OpenAQClient, sensors: list[dict], lookback_days: int) -> list[dict]:
    datetime_from = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    all_measurements: list[dict] = []
    for sensor in sensors:
        sensor_id = sensor["sensor_id"]
        try:
            count = 0
            for raw in client.get_hourly_measurements(
                sensor_id=sensor_id, datetime_from=datetime_from, limit=1000
            ):
                validated = HourlyData.model_validate(raw)
                record = validated.model_dump(mode="json")
                record["sensor_id"] = sensor_id
                record["location_id"] = sensor["location_id"]
                all_measurements.append(record)
                count += 1
            logger.info(
                "  sensor_id=%s (%s @ %s) -> %d hourly records",
                sensor_id,
                sensor["parameter_name"],
                sensor["location_name"],
                count,
            )
        except Exception:
            # One bad sensor shouldn't kill a multi-hour ingestion run. In
            # Phase 4 (Dagster) this becomes a per-asset failure with proper
            # observability instead of a log line -- logged loudly for now.
            logger.exception("Failed to fetch measurements for sensor_id=%s", sensor_id)
    return all_measurements


def write_bronze(records: list[dict], ingest_date: date, bronze_dir: Path = BRONZE_DIR) -> Path:
    out_dir = bronze_dir / "measurements" / f"ingest_date={ingest_date.isoformat()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.json_normalize(records, sep="__")
    out_path = out_dir / "measurements.parquet"
    df.to_parquet(out_path, index=False)
    logger.info("Wrote %d measurement records to %s", len(records), out_path)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract OpenAQ hourly measurements to the bronze layer")
    parser.add_argument("--lookback-days", type=int, default=MEASUREMENT_LOOKBACK_DAYS)
    parser.add_argument(
        "--limit-sensors", type=int, default=None, help="Cap sensor count for a quick test run"
    )
    parser.add_argument(
        "--max-sensors-per-location",
        type=int,
        default=None,
        help="Cap each location to a diverse set of N pollutant sensors",
    )
    args = parser.parse_args()

    locations_path = latest_locations_snapshot()
    sensors = sensor_ids_from_locations(
        locations_path,
        max_sensors_per_location=args.max_sensors_per_location,
    )
    if args.limit_sensors:
        sensors = sensors[: args.limit_sensors]
    logger.info("Fetching hourly measurements for %d sensors", len(sensors))

    client = OpenAQClient()
    records = fetch_measurements(client, sensors, lookback_days=args.lookback_days)
    write_bronze(records, ingest_date=date.today())


if __name__ == "__main__":
    main()
