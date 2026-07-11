"""
Data access layer for the Streamlit app.

Two modes, chosen automatically:
  - LIVE: if airpulse.duckdb exists locally, query it directly (read-only).
    This is what you get running the app on your own machine after Dagster
    has populated the warehouse.
  - SNAPSHOT: otherwise, read the committed Parquet files under
    data/gold_snapshot/ instead. This is what the deployed app on Streamlit
    Community Cloud actually uses -- it has no access to a live DuckDB file
    or a running Dagster instance, only whatever's committed to the repo.

Every query result is wrapped in st.cache_data so repeat interactions
(changing a filter, switching tabs) don't re-hit the database/files on
every rerun -- Streamlit reruns the whole script on almost every interaction,
so this caching is what keeps the app feeling responsive rather than
re-querying on every click.
"""

from __future__ import annotations


import duckdb
import pandas as pd
import streamlit as st

from ingestion.config import PROJECT_ROOT
from warehouse.db import DB_PATH

GOLD_SNAPSHOT_DIR = PROJECT_ROOT / "data" / "gold_snapshot"


def _using_live_db() -> bool:
    return DB_PATH.exists()


def _query(sql: str) -> pd.DataFrame:
    """
    Run a SQL query against whichever backend is available.

    In SNAPSHOT mode, the query still runs through DuckDB -- just an
    in-memory connection with the Parquet files registered as views -- so
    the exact same SQL works unmodified in both modes. This is one of
    DuckDB's nicer properties for a project like this: it's just as happy
    querying Parquet directly as querying its own database file.
    """
    if _using_live_db():
        conn = duckdb.connect(str(DB_PATH), read_only=True)
    else:
        conn = duckdb.connect(":memory:")
        for parquet_file in GOLD_SNAPSHOT_DIR.glob("*.parquet"):
            table_name = parquet_file.stem
            conn.execute(f"CREATE VIEW mart_{table_name} AS SELECT * FROM read_parquet('{parquet_file}')")
        # Snapshot-mode queries reference unqualified table names (no
        # `mart.` prefix, since there's no such schema in an in-memory
        # connection) -- rewrite them so the same SQL string works in both
        # modes without every caller needing to know which mode is active.
        for parquet_file in GOLD_SNAPSHOT_DIR.glob("*.parquet"):
            sql = sql.replace(f"mart.{parquet_file.stem}", f"mart_{parquet_file.stem}")

    try:
        return conn.execute(sql).fetchdf()
    except duckdb.CatalogException:
        # The pipeline has never been run on this machine yet, so `mart`
        # (or a specific mart table) doesn't exist -- this is a genuinely
        # expected first-run state, not a bug, so surface it as "no data"
        # rather than letting a raw stack trace hit the person's screen.
        # The pages themselves are responsible for showing a friendly
        # message when they get an empty frame back.
        return pd.DataFrame()
    finally:
        conn.close()


def data_source_label() -> str:
    """For the footer -- tell the person which mode they're looking at."""
    return "live DuckDB warehouse" if _using_live_db() else "committed snapshot (data/gold_snapshot/)"


@st.cache_data(ttl=300)
def load_daily_city_aqi() -> pd.DataFrame:
    return _query("SELECT * FROM mart.fact_daily_city_aqi")


@st.cache_data(ttl=300)
def load_latest_city_aqi() -> pd.DataFrame:
    """One row per (location, pollutant): the most recent day available for each."""
    return _query(
        """
        SELECT * FROM mart.fact_daily_city_aqi
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY location_key, pollutant_key ORDER BY measured_date DESC
        ) = 1
        """
    )


@st.cache_data(ttl=300)
def load_hourly_trend(location_key: str, pollutant_key: str) -> pd.DataFrame:
    return _query(
        f"""
        SELECT measured_at_utc, aqi, raw_value, value_ugm3, risk_tier
        FROM mart.fact_air_quality_hourly
        WHERE location_key = '{location_key}' AND pollutant_key = '{pollutant_key}'
        ORDER BY measured_at_utc
        """
    )


@st.cache_data(ttl=300)
def load_locations() -> pd.DataFrame:
    return _query("SELECT * FROM mart.dim_location WHERE is_current")


@st.cache_data(ttl=300)
def load_locations_without_recent_aqi() -> pd.DataFrame:
    return _query(
        """
        WITH current_locations AS (
            SELECT
                location_key,
                location_id,
                location_name,
                country_code,
                country_name,
                latitude,
                longitude
            FROM mart.dim_location
            WHERE is_current
        ),
        latest_date AS (
            SELECT MAX(measured_date) AS measured_date
            FROM mart.fact_daily_city_aqi
        ),
        locations_with_current_aqi AS (
            SELECT DISTINCT f.location_key
            FROM mart.fact_daily_city_aqi f
            JOIN latest_date d ON f.measured_date = d.measured_date
        )
        SELECT
            l.location_name,
            l.country_name,
            l.country_code,
            l.latitude,
            l.longitude,
            'No recent AQI data' AS data_status
        FROM current_locations l
        LEFT JOIN locations_with_current_aqi a ON l.location_key = a.location_key
        WHERE a.location_key IS NULL
        ORDER BY l.country_name, l.location_name
        """
    )


@st.cache_data(ttl=300)
def load_pollutants() -> pd.DataFrame:
    return _query("SELECT * FROM mart.dim_pollutant WHERE has_aqi_support")


@st.cache_data(ttl=300)
def pipeline_freshness() -> dict:
    """Metadata for the footer: how current is the data actually showing."""
    df = _query(
        "SELECT MAX(measured_date) AS latest_date, COUNT(DISTINCT location_key) AS num_locations FROM mart.fact_daily_city_aqi"
    )
    if df.empty or pd.isna(df.iloc[0]["latest_date"]):
        return {"latest_date": None, "num_locations": 0}
    return {"latest_date": df.iloc[0]["latest_date"], "num_locations": int(df.iloc[0]["num_locations"])}
