"""
Phase 1 ingestion: pull location + sensor metadata from OpenAQ and land it to
the bronze layer as partitioned Parquet (plus the raw JSON, for auditability).

Run:
    python -m ingestion.extract_locations
    python -m ingestion.extract_locations --countries US IN
    python -m ingestion.extract_locations --limit-locations-per-country 10
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ingestion.config import BRONZE_DIR, TARGET_COUNTRY_ISO_CODES
from ingestion.openaq_client import OpenAQClient
from ingestion.schemas import Location

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _datetime_last_timestamp(location: dict) -> float:
    datetime_last = location.get("datetimeLast") or {}
    utc_value = datetime_last.get("utc")
    if not utc_value:
        return 0.0
    try:
        return datetime.fromisoformat(utc_value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def location_importance_key(location: dict) -> tuple[int, int, int, float, int, int, int, str]:
    """
    Prefer active fixed monitors with useful, not excessive, sensor coverage.

    Ranking purely by "most sensors" can select locations with hundreds of
    duplicate/noisy sensors, which makes scheduled refreshes slow without
    improving the dashboard much. Moderate sensor counts usually give enough
    pollutant coverage while keeping API calls predictable.
    """
    sensors = location.get("sensors") or []
    sensor_count = len(sensors)
    pollutant_count = len({sensor.get("parameter", {}).get("name") for sensor in sensors})
    moderate_sensor_coverage = int(2 <= sensor_count <= 8)
    excessive_sensor_penalty = -max(sensor_count - 8, 0)

    return (
        int(bool(location.get("isMonitor"))),
        int(not bool(location.get("isMobile"))),
        moderate_sensor_coverage,
        _datetime_last_timestamp(location),
        pollutant_count,
        min(sensor_count, 8),
        excessive_sensor_penalty,
        location.get("name") or "",
    )


def fetch_locations(
    client: OpenAQClient, iso_codes: list[str], limit_locations_per_country: Optional[int] = None
) -> list[dict]:
    """Pull + schema-validate locations for each target country."""
    all_locations: list[dict] = []
    for iso in iso_codes:
        logger.info("Fetching locations for country=%s", iso)
        country_locations: list[dict] = []
        for raw in client.get_locations(iso=iso, limit=100):
            # Validate at the ingestion boundary. If OpenAQ changes their
            # response shape, we find out here -- not three layers downstream
            # in a dbt model that silently produces nulls.
            validated = Location.model_validate(raw)
            record = validated.model_dump(mode="json")
            record["_ingested_iso"] = iso
            country_locations.append(record)

        fetched_count = len(country_locations)
        if limit_locations_per_country is not None:
            country_locations = sorted(country_locations, key=location_importance_key, reverse=True)[
                :limit_locations_per_country
            ]
            logger.info(
                "  -> selected %d of %d locations for %s",
                len(country_locations),
                fetched_count,
                iso,
            )
        else:
            logger.info("  -> %d locations for %s", fetched_count, iso)

        all_locations.extend(country_locations)
    return all_locations


def write_bronze(records: list[dict], ingest_date: date, bronze_dir: Path = BRONZE_DIR) -> Path:
    out_dir = bronze_dir / "locations" / f"ingest_date={ingest_date.isoformat()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Raw JSON is the real audit trail -- cheap to keep, and it's what you
    # want on hand if a future flattening bug needs to be debugged against
    # ground truth rather than an already-reshaped DataFrame.
    (out_dir / "raw.json").write_text(json.dumps(records, indent=2, default=str))

    df = pd.json_normalize(records, sep="__")
    out_path = out_dir / "locations.parquet"
    df.to_parquet(out_path, index=False)
    logger.info("Wrote %d locations to %s", len(records), out_path)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract OpenAQ locations to the bronze layer")
    parser.add_argument("--countries", nargs="*", default=TARGET_COUNTRY_ISO_CODES)
    parser.add_argument(
        "--limit-locations-per-country",
        type=int,
        default=None,
        help="Keep only the most useful N locations per country for faster scheduled refreshes",
    )
    args = parser.parse_args()

    client = OpenAQClient()
    records = fetch_locations(
        client,
        args.countries,
        limit_locations_per_country=args.limit_locations_per_country,
    )
    write_bronze(records, ingest_date=date.today())


if __name__ == "__main__":
    main()
