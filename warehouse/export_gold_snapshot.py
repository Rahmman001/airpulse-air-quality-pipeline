"""
Exports the mart layer to Parquet files under data/gold_snapshot/.

This is the concrete implementation of the "hybrid deployment" pattern
documented back in Phase 3: Streamlit Community Cloud can't run a persistent
Dagster process, and the local airpulse.duckdb file is gitignored (it's
fully rebuildable from bronze, so there's no reason to commit it). So the
actual deployed dashboard doesn't read the live DuckDB file at all -- it
reads a committed snapshot of just the mart tables, refreshed on a schedule
by a GitHub Actions job (Phase 6) that runs the pipeline and re-commits
these files.

Run:
    python -m warehouse.export_gold_snapshot
"""

from __future__ import annotations

import logging
from pathlib import Path

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
    conn = get_connection(read_only=True)
    results: dict[str, int] = {}
    try:
        for qualified_name in TABLES_TO_EXPORT:
            table_name = qualified_name.split(".")[-1]
            out_path = output_dir / f"{table_name}.parquet"
            conn.execute(f"COPY {qualified_name} TO '{out_path}' (FORMAT PARQUET)")
            count = conn.execute(f"SELECT COUNT(*) FROM {qualified_name}").fetchone()[0]
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
