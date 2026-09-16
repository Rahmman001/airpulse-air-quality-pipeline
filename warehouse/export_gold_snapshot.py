"""
Exports the mart layer to Parquet files under data/gold_snapshot/.

These Parquet snapshots provide an offline, portable fallback for the FastAPI server,
unit tests, and edge exporters without requiring a live DuckDB file on disk.

Run:
    python -m warehouse.export_gold_snapshot
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from ingestion.config import PROJECT_ROOT
from warehouse.db import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

GOLD_SNAPSHOT_DIR = PROJECT_ROOT / "data" / "gold_snapshot"

# Only the tables the dashboard actually queries -- no reason to export the
# whole warehouse, and keeping this list explicit means it's obvious exactly
# what the deployed app depends on.
TABLES_TO_EXPORT = [
    "mart.fact_daily_city_aqi",
    "mart.fact_air_quality_hourly",
    "mart.dim_location",
    "mart.dim_pollutant",
]


def export_gold_snapshot(output_dir: Path = GOLD_SNAPSHOT_DIR) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    from warehouse.db import DB_PATH

    if not DB_PATH.exists():
        logger.info(
            "Live warehouse %s does not exist; inspecting existing snapshots in %s",
            DB_PATH,
            output_dir,
        )
        results: dict[str, int] = {}
        for qualified_name in TABLES_TO_EXPORT:
            table_name = qualified_name.split(".")[-1]
            out_path = output_dir / f"{table_name}.parquet"
            if out_path.exists():
                c = duckdb.connect()
                row = c.execute(
                    f"SELECT COUNT(*) FROM read_parquet('{out_path}')"
                ).fetchone()
                results[table_name] = int(row[0]) if row else 0
                c.close()
        return results

    conn = get_connection(read_only=True)
    results: dict[str, int] = {}
    try:
        for qualified_name in TABLES_TO_EXPORT:
            table_name = qualified_name.split(".")[-1]
            out_path = output_dir / f"{table_name}.parquet"
            conn.execute(f"COPY {qualified_name} TO '{out_path}' (FORMAT PARQUET)")
            row = conn.execute(f"SELECT COUNT(*) FROM {qualified_name}").fetchone()
            count = int(row[0]) if row else 0
            results[table_name] = count
            logger.info("Exported %s: %d rows -> %s", qualified_name, count, out_path)
    finally:
        conn.close()
    return results


def main() -> None:
    results = export_gold_snapshot()
    logger.info("Gold snapshot export complete: %s", results)


if __name__ == "__main__":
    main()
