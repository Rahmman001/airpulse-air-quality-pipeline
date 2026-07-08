"""
Phase 2: load bronze-layer Parquet files into a DuckDB `raw` schema.

This is deliberately a thin layer -- it does NOT clean, dedupe, or reshape
anything. That's dbt's job (Phase 3), and keeping this boundary sharp is a
core data-engineering principle: raw stays raw, so you can always re-run
transformations without re-hitting the source API.

Two loading strategies are supported:
  - full refresh (default): re-read every partition under a source, replace
    the raw table entirely. Simple, correct, and fine at this data volume.
  - incremental append: only load partitions newer than what's already
    loaded. Useful once bronze accumulates enough history that a full
    refresh gets slow -- included here as a realistic "how would this scale"
    answer for interviews, even though full refresh is what you'll use day
    to day at this project's size.

Run:
    python -m warehouse.load_raw
    python -m warehouse.load_raw --mode incremental
"""

from __future__ import annotations

import argparse
import logging

import duckdb

from ingestion.config import BRONZE_DIR
from warehouse.db import get_connection, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Maps: raw table name -> glob pattern of bronze Parquet files that feed it
SOURCES = {
    "locations": BRONZE_DIR / "locations" / "ingest_date=*" / "locations.parquet",
    "measurements": BRONZE_DIR / "measurements" / "ingest_date=*" / "measurements.parquet",
}


def _glob_pattern(path) -> str:
    """DuckDB's read_parquet wants a glob string, not a Path object."""
    return str(path)


def full_refresh(conn: duckdb.DuckDBPyConnection, table_name: str, glob: str) -> int:
    """
    Replace raw.<table_name> entirely with everything currently in bronze.

    read_parquet(..., filename=true) tags each row with which physical file
    it came from -- handy for debugging "which ingestion run produced this
    row" later, and it costs nothing to keep. DuckDB also auto-detects the
    hive-style `ingest_date=YYYY-MM-DD` folder structure and adds a real,
    typed `ingest_date` DATE column for free -- no manual parsing needed,
    and it's what incremental_append() filters on below.
    """
    conn.execute(
        f"""
        CREATE OR REPLACE TABLE raw.{table_name} AS
        SELECT *, filename AS _source_file
        FROM read_parquet('{glob}', filename=true, union_by_name=true)
        """
    )
    count = conn.execute(f"SELECT COUNT(*) FROM raw.{table_name}").fetchone()[0]
    return count


def incremental_append(conn: duckdb.DuckDBPyConnection, table_name: str, glob: str) -> int:
    """
    Only load partitions whose ingest_date is newer than what's already in
    raw.<table_name>. Falls back to a full refresh if the table doesn't
    exist yet.

    Note: this appends full partitions, not row-level dedup -- if you re-run
    an ingest_date that already loaded, you'll get duplicates. dbt's staging
    layer is responsible for deduping on the real business key
    (sensor_id + timestamp), which is the correct place for that logic to
    live, not the loader.
    """
    table_exists = (
        conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables " "WHERE table_schema = 'raw' AND table_name = ?",
            [table_name],
        ).fetchone()[0]
        > 0
    )

    if not table_exists:
        logger.info("raw.%s doesn't exist yet -- doing a full refresh instead", table_name)
        return full_refresh(conn, table_name, glob)

    max_loaded = conn.execute(
        f"SELECT COALESCE(MAX(ingest_date), DATE '1970-01-01') FROM raw.{table_name}"
    ).fetchone()[0]

    conn.execute(
        f"""
        INSERT INTO raw.{table_name}
        SELECT *, filename AS _source_file
        FROM read_parquet('{glob}', filename=true, union_by_name=true)
        WHERE ingest_date > ?
        """,
        [max_loaded],
    )

    count = conn.execute(f"SELECT COUNT(*) FROM raw.{table_name}").fetchone()[0]
    return count


def load_all(mode: str = "full") -> dict[str, int]:
    init_db()
    conn = get_connection()
    results: dict[str, int] = {}
    try:
        for table_name, path in SOURCES.items():
            glob = _glob_pattern(path)
            logger.info("Loading raw.%s from %s (mode=%s)", table_name, glob, mode)
            if mode == "incremental":
                count = incremental_append(conn, table_name, glob)
            else:
                count = full_refresh(conn, table_name, glob)
            logger.info("  -> raw.%s now has %d rows", table_name, count)
            results[table_name] = count
    finally:
        conn.close()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Load bronze Parquet into DuckDB raw schema")
    parser.add_argument("--mode", choices=["full", "incremental"], default="full")
    args = parser.parse_args()
    load_all(mode=args.mode)


if __name__ == "__main__":
    main()
