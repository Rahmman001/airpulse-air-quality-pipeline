"""
Cloudflare R2 Object Storage Integration for AirPulse.

Leverages DuckDB's native httpfs extension to read and write Parquet snapshots
directly to Cloudflare R2 (S3-compatible) with zero new Python dependencies.

Features:
- Auto-detects R2 credentials from environment or .env
- Exports mart tables directly to s3://<bucket>/gold/<table_name>.parquet
- Provides seamless local fallback to data/gold_snapshot/ when R2 is not configured
- Configures DuckDB connection for direct querying of remote R2 Parquet files
"""

from __future__ import annotations

import logging
import os

import duckdb

from ingestion.config import PROJECT_ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

GOLD_SNAPSHOT_DIR = PROJECT_ROOT / "data" / "gold_snapshot"

TABLES_TO_EXPORT = [
    "mart.fact_daily_city_aqi",
    "mart.fact_air_quality_hourly",
    "mart.dim_location",
    "mart.dim_pollutant",
]


def get_r2_config() -> dict[str, str] | None:
    """Retrieve Cloudflare R2 credentials from environment or .env file."""
    account_id = os.environ.get("R2_ACCOUNT_ID", "").strip()
    access_key = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    bucket = os.environ.get("R2_BUCKET_NAME", "airpulse-lakehouse").strip()

    # If missing in os.environ, attempt loading from .env
    if not (account_id and access_key and secret_key):
        env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k == "R2_ACCOUNT_ID" and not account_id:
                    account_id = v
                elif k == "R2_ACCESS_KEY_ID" and not access_key:
                    access_key = v
                elif k == "R2_SECRET_ACCESS_KEY" and not secret_key:
                    secret_key = v
                elif k == "R2_BUCKET_NAME" and bucket == "airpulse-lakehouse" and v:
                    bucket = v

    if not (account_id and access_key and secret_key):
        return None

    # Check for placeholder values
    if "your_" in account_id.lower() or "your_" in access_key.lower():
        return None

    return {
        "account_id": account_id,
        "access_key_id": access_key,
        "secret_access_key": secret_key,
        "bucket_name": bucket,
        "endpoint": f"{account_id}.r2.cloudflarestorage.com",
    }


def is_r2_configured() -> bool:
    """Check if valid Cloudflare R2 credentials are present."""
    return get_r2_config() is not None


def configure_duckdb_r2(
    conn: duckdb.DuckDBPyConnection, config: dict[str, str] | None = None
) -> str:
    """Configure a DuckDB connection with Cloudflare R2 S3-compatible credentials."""
    cfg = config or get_r2_config()
    if not cfg:
        raise ValueError(
            "Cloudflare R2 credentials are not configured in environment or .env"
        )

    conn.execute("INSTALL httpfs; LOAD httpfs;")
    endpoint = cfg["endpoint"].replace("'", "''")
    access_key = cfg["access_key_id"].replace("'", "''")
    secret_key = cfg["secret_access_key"].replace("'", "''")
    conn.execute(f"SET s3_endpoint = '{endpoint}';")
    conn.execute(f"SET s3_access_key_id = '{access_key}';")
    conn.execute(f"SET s3_secret_access_key = '{secret_key}';")
    conn.execute("SET s3_url_style = 'path';")
    conn.execute("SET s3_use_ssl = true;")
    return cfg["bucket_name"]


def export_to_r2(conn: duckdb.DuckDBPyConnection | None = None) -> dict[str, int]:
    """Export analytical mart tables directly to Cloudflare R2."""
    cfg = get_r2_config()
    if not cfg:
        raise RuntimeError(
            "Cannot export to R2: Missing credentials in environment or .env"
        )

    close_after = False
    if conn is None:
        from warehouse.db import get_connection

        conn = get_connection(read_only=True)
        close_after = True

    try:
        bucket = configure_duckdb_r2(conn, cfg)
        results: dict[str, int] = {}
        for qualified_name in TABLES_TO_EXPORT:
            table_name = qualified_name.split(".")[-1]
            r2_target = f"s3://{bucket}/gold/{table_name}.parquet"
            conn.execute(f"COPY {qualified_name} TO '{r2_target}' (FORMAT PARQUET)")
            row = conn.execute(f"SELECT COUNT(*) FROM {qualified_name}").fetchone()
            count = int(row[0]) if row else 0
            results[table_name] = count
            logger.info(
                "Exported to Cloudflare R2: %s (%d rows) -> %s",
                qualified_name,
                count,
                r2_target,
            )
        return results
    finally:
        if close_after:
            conn.close()


def sync_snapshots(force_local: bool = False) -> dict[str, int]:
    """
    Sync gold snapshots.
    If Cloudflare R2 is configured and force_local is False, exports to R2.
    Always exports local fallback to data/gold_snapshot/ as well.
    """
    from warehouse.export_gold_snapshot import export_gold_snapshot

    local_results = export_gold_snapshot()

    if not force_local and is_r2_configured():
        logger.info(
            "Cloudflare R2 credentials detected. Syncing gold snapshots to Cloudflare R2..."
        )
        try:
            r2_results = export_to_r2()
            logger.info("Cloudflare R2 sync completed successfully: %s", r2_results)
            return r2_results
        except Exception as e:
            logger.warning(
                "Cloudflare R2 export encountered an issue (%s); local snapshots preserved.",
                e,
            )
            return local_results
    else:
        logger.info(
            "Cloudflare R2 not configured; gold snapshots saved locally to %s",
            GOLD_SNAPSHOT_DIR,
        )
        return local_results


def main() -> None:
    results = sync_snapshots()
    logger.info("Snapshot sync complete: %s", results)


if __name__ == "__main__":
    main()
