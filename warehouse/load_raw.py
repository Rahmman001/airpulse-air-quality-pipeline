"""
Phase 2: load bronze-layer Parquet files into a DuckDB `raw` schema.

This is deliberately a thin layer -- it does NOT clean, dedupe, or reshape
anything. That's dbt's job (Phase 3), and keeping this boundary sharp is a
core data-engineering principle: raw stays raw, so you can always re-run
transformations without re-hitting the source API.

Run:
    python -m warehouse.load_raw
"""

from __future__ import annotations

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


def full_refresh(conn: duckdb.DuckDBPyConnection, table_name: str, glob: str) -> int:
    """
    Replace raw.<table_name> entirely with everything currently in bronze.

    read_parquet(..., filename=true) tags each row with which physical file
    it came from -- handy for debugging "which ingestion run produced this
    row" later, and it costs nothing to keep. DuckDB also auto-detects the
    hive-style `ingest_date=YYYY-MM-DD` folder structure and adds a real,
    typed `ingest_date` DATE column for free -- no manual parsing needed.
    """
    conn.execute(
        f"""
        CREATE OR REPLACE TABLE raw.{table_name} AS
        SELECT *, filename AS _source_file
        FROM read_parquet('{glob}', filename=true, union_by_name=true)
        """
    )
    row = conn.execute(f"SELECT COUNT(*) FROM raw.{table_name}").fetchone()
    return int(row[0]) if row else 0


def load_all() -> dict[str, int]:
    init_db()
    conn = get_connection()
    results: dict[str, int] = {}
    try:
        for table_name, path in SOURCES.items():
            glob = str(path)
            logger.info("Loading raw.%s from %s", table_name, glob)
            count = full_refresh(conn, table_name, glob)
            logger.info("  -> raw.%s now has %d rows", table_name, count)
            results[table_name] = count
    finally:
        conn.close()
    return results


def main() -> None:
    load_all()


if __name__ == "__main__":
    main()
