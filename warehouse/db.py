"""
DuckDB connection management.

DuckDB is an embedded OLAP engine — there's no separate server process.
A .duckdb file acts like a SQLite file: it's just a local file that holds
the database. This simplifies deployment (especially for Streamlit on Community
Cloud, which can't run a persistent server process), but it means you need to
be thoughtful about concurrent access:

  - WRITES: only one writer at a time (DuckDB's MVCC model enforces this)
  - READS: multiple readers can run concurrently with each other,
           but not with a write

In practice, for this project:
  - Dagster orchestrates the write (ingestion + dbt models)
  - Streamlit only reads — it never writes
  - We sidestep the single-writer limit by treating reads as read-only
    queries against a snapshot (gold-layer Parquet exports, not the live file)

For a real production system: use Snowflake / BigQuery / Redshift instead,
where server-based MVCC handles concurrent reads and writes elegantly.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

# Where the actual .duckdb file lives (the "warehouse" itself)
DB_PATH = Path(__file__).resolve().parents[1] / "airpulse.duckdb"


def get_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """
    Get a DuckDB connection.

    Args:
        read_only: if True, forbid writes (useful for Streamlit to fail fast
                   if code accidentally tries to write). Default False for batch
                   processes that intentionally write.

    Returns:
        A DuckDB connection object.
    """
    # read_only must be passed to connect() itself -- it's a connection-mode
    # flag, not a session setting you can SET after the fact. A read-only
    # connection also requires the file to already exist, which is exactly
    # the failure mode we want: if init_db() hasn't run yet, fail loudly
    # instead of silently creating an empty database.
    return duckdb.connect(str(DB_PATH), read_only=read_only)


def init_db() -> None:
    """Idempotent schema initialization — create schemas if they don't exist."""
    conn = get_connection()
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
    conn.execute("CREATE SCHEMA IF NOT EXISTS staging")
    conn.execute("CREATE SCHEMA IF NOT EXISTS mart")
    conn.close()
