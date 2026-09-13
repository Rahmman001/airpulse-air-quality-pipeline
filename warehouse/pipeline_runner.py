"""
Unified End-to-End Pipeline Runner for AirPulse.

Sequences:
  1. Bronze Extraction (Live OpenAQ API if key configured, or rich global multi-city seed)
  2. DuckDB Raw Load (warehouse.load_raw)
  3. dbt Model Transformations & Tests (dbt build)
  4. Gold Mart Parquet Snapshot Export (warehouse.export_gold_snapshot)
  5. API In-Memory Cache Invalidation (app.utils.data.clear_cache)

Run:
    python -m warehouse.pipeline_runner
    python -m warehouse.pipeline_runner --offline
    python -m warehouse.pipeline_runner --live
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from ingestion.config import PROJECT_ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("airpulse.pipeline")

DBT_PROJECT_DIR = PROJECT_ROOT / "dbt_project"


def has_valid_openaq_key() -> bool:
    """Check if a non-placeholder OPENAQ_API_KEY is available in env or .env file."""
    # Check current environment
    if "OPENAQ_API_KEY" in os.environ:
        key = os.environ["OPENAQ_API_KEY"]
        return bool(key and key.strip() and "your-openaq-api-key" not in key.lower())

    # Check .env file
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENAQ_API_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val and "your-openaq-api-key" not in val.lower():
                    return True
    return False


def run_bronze_extraction(mode: str) -> None:
    """Run either live OpenAQ API extraction or synthetic global seed generation."""
    if mode == "live":
        logger.info("[1/5] Extracting live data from OpenAQ API...")
        from ingestion.extract_locations import main as extract_locations_main
        from ingestion.extract_measurements import main as extract_measurements_main

        # Isolate sys.argv so sub-parsers don't fail on --live / --offline flags
        orig_argv = list(sys.argv)
        try:
            sys.argv = [orig_argv[0]]
            extract_locations_main()
            extract_measurements_main()
        finally:
            sys.argv = orig_argv
    else:
        logger.info("[1/5] Generating rich global multi-city telemetry seed (25 stations, 6 continents)...")
        from scripts_dev.generate_global_seed import main as generate_seed_main

        generate_seed_main()


def run_raw_loader() -> dict[str, int]:
    """Load bronze Parquet partitions into DuckDB raw schema."""
    logger.info("[2/5] Loading bronze data into DuckDB raw schema...")
    from warehouse.load_raw import load_all

    counts = load_all()
    for table, count in counts.items():
        logger.info("  -> raw.%s: %d rows", table, count)
    return counts


def run_dbt() -> None:
    """Execute dbt build (staging views, intermediate views, snapshot, marts, tests)."""
    logger.info("[3/5] Building dbt models and running schema/data quality tests...")
    
    # Ensure dbt executable is located
    dbt_exec = shutil.which("dbt") or str(Path(sys.executable).with_name("dbt"))
    
    # Ensure profiles.yml exists in dbt_project
    profiles_yml = DBT_PROJECT_DIR / "profiles.yml"
    if not profiles_yml.exists():
        example_profile = DBT_PROJECT_DIR / "profiles.yml.example"
        if example_profile.exists():
            profiles_yml.write_text(example_profile.read_text())

    # Execute dbt build with cwd set to dbt_project directory so relative path resolves to repo root
    cmd = [dbt_exec, "build", "--profiles-dir", "."]
    res = subprocess.run(cmd, cwd=str(DBT_PROJECT_DIR), capture_output=True, text=True)
    if res.returncode != 0:
        logger.error("dbt build failed:\n%s\n%s", res.stdout, res.stderr)
        raise RuntimeError("dbt build failed during pipeline execution")
    
    logger.info("dbt build completed successfully with all tests passing.")


def run_gold_export() -> dict[str, int]:
    """Export mart tables to data/gold_snapshot/*.parquet."""
    logger.info("[4/5] Exporting mart tables to data/gold_snapshot Parquet files...")
    from warehouse.export_gold_snapshot import export_gold_snapshot

    counts = export_gold_snapshot()
    for table, count in counts.items():
        logger.info("  -> %s: %d rows", table, count)
    return counts


def clear_api_cache() -> None:
    """Invalidate FastAPI / analytical data memory cache."""
    logger.info("[5/5] Invalidation of operational memory caches...")
    try:
        from app.utils.data import clear_cache

        clear_cache()
        logger.info("  -> In-process cache cleared.")
    except Exception as e:
        logger.warning("Could not clear in-process cache: %s", e)

    import urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/api/v1/cache/clear", data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=2):
            logger.info("  -> FastAPI server memory cache cleared.")
    except Exception:
        pass


def run_pipeline(force_mode: str | None = None) -> dict[str, int]:
    """Execute the full end-to-end pipeline."""
    if force_mode:
        mode = force_mode
    else:
        mode = "live" if has_valid_openaq_key() else "offline"

    logger.info("Starting AirPulse end-to-end data pipeline in '%s' mode.", mode)

    run_bronze_extraction(mode)
    raw_counts = run_raw_loader()
    run_dbt()
    gold_counts = run_gold_export()
    clear_api_cache()

    try:
        from warehouse.export_static_data import export_all
        export_all()
    except Exception as e:
        logger.warning("Could not export static data: %s", e)

    logger.info("AirPulse pipeline completed successfully.")
    return gold_counts


def main() -> None:
    parser = argparse.ArgumentParser(description="AirPulse End-to-End Pipeline Orchestrator")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--live", action="store_true", help="Force live extraction from OpenAQ API")
    group.add_argument("--offline", action="store_true", help="Force offline global seed generation")
    args = parser.parse_args()

    mode = "live" if args.live else ("offline" if args.offline else None)
    run_pipeline(force_mode=mode)


if __name__ == "__main__":
    main()
