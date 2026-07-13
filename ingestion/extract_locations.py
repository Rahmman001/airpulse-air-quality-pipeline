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

from ingestion.config import (
    BRONZE_DIR,
    CITY_FALLBACK_STATIONS_BY_COUNTRY,
    COUNTRY_LOCATION_LIMITS,
    IMPORTANT_CITIES_BY_COUNTRY,
    TARGET_COUNTRY_ISO_CODES,
)
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


def _location_search_text(location: dict) -> str:
    parts = [
        location.get("name"),
        location.get("locality"),
        location.get("country", {}).get("name"),
    ]
    return " ".join(str(part).lower() for part in parts if part)


def city_priority_score(location: dict, iso: str) -> int:
    return int(city_priority_name(location, iso) is not None)


def city_priority_name(location: dict, iso: str) -> Optional[str]:
    search_text = _location_search_text(location)
    cities = IMPORTANT_CITIES_BY_COUNTRY.get(iso, {})
    for city, aliases in cities.items():
        if any(alias.lower() in search_text for alias in aliases):
            return city
    return None


def location_importance_key(
    location: dict, iso: str = ""
) -> tuple[int, int, int, int, float, int, int, int, str]:
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
        _datetime_last_timestamp(location),
        city_priority_score(location, iso),
        moderate_sensor_coverage,
        pollutant_count,
        min(sensor_count, 8),
        excessive_sensor_penalty,
        location.get("name") or "",
    )


def parse_country_location_limits(raw_limits: list[str]) -> dict[str, int]:
    limits: dict[str, int] = {}
    for raw_limit in raw_limits:
        if "=" not in raw_limit:
            raise ValueError(
                f"Invalid country location limit {raw_limit!r}. Use ISO=NUMBER, for example IN=20."
            )
        iso, limit = raw_limit.split("=", 1)
        iso = iso.strip().upper()
        if not iso:
            raise ValueError(f"Invalid country location limit {raw_limit!r}: missing ISO code.")
        try:
            parsed_limit = int(limit)
        except ValueError as exc:
            raise ValueError(
                f"Invalid country location limit {raw_limit!r}: limit must be an integer."
            ) from exc
        if parsed_limit < 1:
            raise ValueError(f"Invalid country location limit {raw_limit!r}: limit must be at least 1.")
        limits[iso] = parsed_limit
    return limits


def select_locations_for_country(locations: list[dict], iso: str, limit: int) -> list[dict]:
    ranked = sorted(
        locations,
        key=lambda location: location_importance_key(location, iso),
        reverse=True,
    )
    city_fallback_limit = CITY_FALLBACK_STATIONS_BY_COUNTRY.get(iso, 1)
    selected: list[dict] = []
    selected_ids: set[int] = set()
    city_counts: dict[str, int] = {}

    for location in ranked:
        city = city_priority_name(location, iso)
        if city is None or city_counts.get(city, 0) >= city_fallback_limit:
            continue
        selected.append(location)
        selected_ids.add(location["id"])
        city_counts[city] = city_counts.get(city, 0) + 1
        if len(selected) == limit:
            return selected

    for location in ranked:
        if location["id"] in selected_ids:
            continue
        selected.append(location)
        if len(selected) == limit:
            return selected

    return selected


def fetch_locations(
    client: OpenAQClient,
    iso_codes: list[str],
    limit_locations_per_country: Optional[int] = None,
    country_location_limits: Optional[dict[str, int]] = None,
) -> list[dict]:
    """Pull + schema-validate locations for each target country."""
    all_locations: list[dict] = []
    country_location_limits = country_location_limits or {}
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
        country_limit = country_location_limits.get(iso, limit_locations_per_country)
        if country_limit is not None:
            country_locations = select_locations_for_country(country_locations, iso, country_limit)
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
    parser.add_argument(
        "--country-location-limit",
        action="append",
        default=[],
        metavar="ISO=NUMBER",
        help="Override the location cap for one country, e.g. IN=20. Can be passed more than once.",
    )
    args = parser.parse_args()

    country_location_limits = parse_country_location_limits(args.country_location_limit)
    if args.limit_locations_per_country is not None:
        country_location_limits = {**COUNTRY_LOCATION_LIMITS, **country_location_limits}
    client = OpenAQClient()
    records = fetch_locations(
        client,
        args.countries,
        limit_locations_per_country=args.limit_locations_per_country,
        country_location_limits=country_location_limits,
    )
    write_bronze(records, ingest_date=date.today())


if __name__ == "__main__":
    main()
