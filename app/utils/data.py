from __future__ import annotations

from functools import wraps
import logging
import time
from typing import Any, Callable

import duckdb
import pandas as pd

from ingestion.config import PROJECT_ROOT
from warehouse.db import DB_PATH

logger = logging.getLogger(__name__)

GOLD_SNAPSHOT_DIR = PROJECT_ROOT / "data" / "gold_snapshot"

_ALL_CACHES: list[dict[Any, Any]] = []


def clear_cache() -> None:
    """Clear all in-memory data caches."""
    for c in _ALL_CACHES:
        c.clear()


def ttl_cache(ttl_seconds: int = 300) -> Callable[..., Any]:
    """Lightweight in-memory TTL cache decorator (stdlib-only, thread-safe for reads)."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        cache: dict[Any, tuple[Any, float]] = {}
        _ALL_CACHES.append(cache)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            if key in cache:
                val, timestamp = cache[key]
                if now - timestamp < ttl_seconds:
                    return val
            result = func(*args, **kwargs)
            cache[key] = (result, now)
            return result

        wrapper.clear = cache.clear  # type: ignore[attr-defined]
        return wrapper

    return decorator


def data_source_label() -> str:
    """For the footer -- tell the person which mode they're looking at."""
    if DB_PATH.exists():
        return "live DuckDB warehouse"
    from warehouse.r2_storage import is_r2_configured

    if is_r2_configured():
        return "Cloudflare R2 lakehouse (remote Parquet)"
    return "committed snapshot (data/gold_snapshot/)"


def _query(sql: str, params: list[Any] | None = None) -> pd.DataFrame:
    if DB_PATH.exists():
        conn = duckdb.connect(str(DB_PATH), read_only=True)
    else:
        conn = duckdb.connect(":memory:")
        conn.execute("CREATE SCHEMA IF NOT EXISTS mart")
        from warehouse.r2_storage import configure_duckdb_r2, get_r2_config

        r2_cfg = get_r2_config()
        if r2_cfg:
            try:
                bucket = configure_duckdb_r2(conn, r2_cfg)
                for tbl in (
                    "fact_daily_city_aqi",
                    "fact_air_quality_hourly",
                    "dim_location",
                    "dim_pollutant",
                ):
                    conn.execute(
                        f"CREATE VIEW mart.{tbl} AS SELECT * FROM read_parquet('s3://{bucket}/gold/{tbl}.parquet')"
                    )
            except Exception as e:
                logger.warning(
                    "Failed to query Cloudflare R2 (%s); falling back to local snapshots.",
                    e,
                )
                for f in GOLD_SNAPSHOT_DIR.glob("*.parquet"):
                    conn.execute(
                        f"CREATE VIEW mart.{f.stem} AS SELECT * FROM read_parquet('{f}')"
                    )
        else:
            for f in GOLD_SNAPSHOT_DIR.glob("*.parquet"):
                conn.execute(
                    f"CREATE VIEW mart.{f.stem} AS SELECT * FROM read_parquet('{f}')"
                )

    try:
        return (
            conn.execute(sql, params).fetchdf()
            if params
            else conn.execute(sql).fetchdf()
        )
    except duckdb.CatalogException:
        return pd.DataFrame()
    finally:
        conn.close()


@ttl_cache(ttl_seconds=300)
def load_latest_city_aqi() -> pd.DataFrame:
    """One row per (location, pollutant): the most recent day available for each."""
    df = _query(
        """
        SELECT * FROM mart.fact_daily_city_aqi
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY location_key, pollutant_key ORDER BY measured_date DESC
        ) = 1
        """
    )
    if not df.empty and "risk_tier" not in df.columns and "avg_aqi" in df.columns:
        from app.utils.risk_tiers import RISK_TIER_ORDER

        df["risk_tier"] = pd.cut(
            df["avg_aqi"],
            bins=[-1, 50, 100, 150, 200, 300, 10_000],
            labels=RISK_TIER_ORDER,
        ).astype(str)
    return df


@ttl_cache(ttl_seconds=300)
def load_hourly_trend(location_key: str, pollutant_key: str) -> pd.DataFrame:
    return _query(
        """
        SELECT measured_at_utc, aqi, raw_value, value_ugm3, risk_tier
        FROM mart.fact_air_quality_hourly
        WHERE location_key = ? AND pollutant_key = ?
        ORDER BY measured_at_utc
        """,
        [location_key, pollutant_key],
    )


@ttl_cache(ttl_seconds=300)
def load_locations() -> pd.DataFrame:
    return _query("SELECT * FROM mart.dim_location WHERE is_current")


@ttl_cache(ttl_seconds=300)
def load_locations_without_recent_aqi() -> pd.DataFrame:
    locations = load_locations()
    latest = load_latest_city_aqi()
    if locations.empty:
        return pd.DataFrame()
    active_keys: list = list(latest["location_key"]) if not latest.empty else []
    missing = locations.loc[~locations["location_key"].isin(active_keys)].copy()
    if missing.empty:
        return pd.DataFrame()
    missing["data_status"] = "No recent AQI data"
    cols = [
        "location_name",
        "country_name",
        "country_code",
        "latitude",
        "longitude",
        "data_status",
    ]
    return missing.loc[:, cols].sort_values(by=["country_name", "location_name"])


@ttl_cache(ttl_seconds=300)
def load_pollutants() -> pd.DataFrame:
    return _query("SELECT * FROM mart.dim_pollutant WHERE has_aqi_support")


@ttl_cache(ttl_seconds=300)
def pipeline_freshness() -> dict:
    df = _query(
        "SELECT MAX(measured_date) AS latest_date, COUNT(DISTINCT location_key) AS num_locations "
        "FROM mart.fact_daily_city_aqi"
    )
    ts_df = _query(
        "SELECT MAX(measured_at_utc) AS latest_ts FROM mart.fact_air_quality_hourly"
    )
    latest_ts = None
    if not ts_df.empty and pd.notna(ts_df.iloc[0]["latest_ts"]):
        latest_ts = str(ts_df.iloc[0]["latest_ts"])

    if df.empty or pd.isna(df.iloc[0]["latest_date"]):
        return {"latest_date": None, "latest_time": latest_ts, "num_locations": 0}
    row = df.iloc[0]
    return {
        "latest_date": row["latest_date"],
        "latest_time": latest_ts,
        "num_locations": int(row["num_locations"]),
    }
