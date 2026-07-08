"""
Phase 1 ingestion: pull location + sensor metadata from OpenAQ and land it to
the bronze layer as partitioned Parquet (plus the raw JSON, for auditability).

Run:
    python -m ingestion.extract_locations
    python -m ingestion.extract_locations --countries US IN
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path

import pandas as pd

from ingestion.config import BRONZE_DIR, TARGET_COUNTRY_ISO_CODES
from ingestion.openaq_client import OpenAQClient
from ingestion.schemas import Location

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def fetch_locations(client: OpenAQClient, iso_codes: list[str]) -> list[dict]:
    """Pull + schema-validate locations for each target country."""
    all_locations: list[dict] = []
    for iso in iso_codes:
        logger.info("Fetching locations for country=%s", iso)
        count = 0
        for raw in client.get_locations(iso=iso, limit=100):
            # Validate at the ingestion boundary. If OpenAQ changes their
            # response shape, we find out here -- not three layers downstream
            # in a dbt model that silently produces nulls.
            validated = Location.model_validate(raw)
            record = validated.model_dump(mode="json")
            record["_ingested_iso"] = iso
            all_locations.append(record)
            count += 1
        logger.info("  -> %d locations for %s", count, iso)
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
    args = parser.parse_args()

    client = OpenAQClient()
    records = fetch_locations(client, args.countries)
    write_bronze(records, ingest_date=date.today())


if __name__ == "__main__":
    main()
