"""
Dagster assets wrapping the Phase 1/2 ingestion and loading code. These are
the assets upstream of dbt -- Dagster treats "pull from OpenAQ" and "load
into DuckDB" as first-class, observable, retriable units of work with their
own metadata and freshness, rather than opaque steps inside a cron script.

Deliberately thin wrappers: all the real logic (pagination, retry, pydantic
validation, dedup) already lives in ingestion/ and warehouse/ and is already
covered by the Phase 1-3 test suite. These asset functions just call that
existing, tested code and report what happened -- they don't reimplement it.
"""

from datetime import date

from dagster import AssetExecutionContext, AssetKey, AssetOut, MaterializeResult, asset, multi_asset

import ingestion.config as ingestion_config
from ingestion.extract_locations import fetch_locations
from ingestion.extract_locations import write_bronze as write_locations_bronze
from ingestion.extract_measurements import (
    fetch_measurements,
    latest_locations_snapshot,
    sensor_ids_from_locations,
)
from ingestion.extract_measurements import write_bronze as write_measurements_bronze
from ingestion.openaq_client import OpenAQClient
from warehouse.load_raw import load_all


@asset(group_name="ingestion", compute_kind="python")
def raw_locations(context: AssetExecutionContext) -> MaterializeResult:
    """Pull location + sensor metadata from OpenAQ into the bronze layer."""
    client = OpenAQClient()
    records = fetch_locations(client, ingestion_config.TARGET_COUNTRY_ISO_CODES)
    # bronze_dir is passed explicitly (reading the config module's current
    # attribute) rather than relying on write_bronze()'s own default, which
    # is bound at function-definition time and would silently ignore a
    # later-changed ingestion_config.BRONZE_DIR (e.g. in tests).
    out_path = write_locations_bronze(
        records, ingest_date=date.today(), bronze_dir=ingestion_config.BRONZE_DIR
    )
    context.log.info("Wrote %d locations to %s", len(records), out_path)
    return MaterializeResult(
        metadata={
            "num_locations": len(records),
            "countries": ", ".join(ingestion_config.TARGET_COUNTRY_ISO_CODES),
            "bronze_path": str(out_path),
        }
    )


@asset(group_name="ingestion", compute_kind="python", deps=[raw_locations])
def raw_measurements(context: AssetExecutionContext) -> MaterializeResult:
    """Pull hourly measurements for every sensor found in the latest locations snapshot."""
    locations_path = latest_locations_snapshot(bronze_dir=ingestion_config.BRONZE_DIR)
    sensors = sensor_ids_from_locations(locations_path)
    client = OpenAQClient()
    records = fetch_measurements(client, sensors, lookback_days=ingestion_config.MEASUREMENT_LOOKBACK_DAYS)
    out_path = write_measurements_bronze(
        records, ingest_date=date.today(), bronze_dir=ingestion_config.BRONZE_DIR
    )
    context.log.info("Wrote %d measurement records to %s", len(records), out_path)
    return MaterializeResult(
        metadata={
            "num_sensors_queried": len(sensors),
            "num_measurements": len(records),
            "lookback_days": ingestion_config.MEASUREMENT_LOOKBACK_DAYS,
            "bronze_path": str(out_path),
        }
    )


@multi_asset(
    outs={
        "raw_locations_table": AssetOut(key=AssetKey(["raw", "locations"]), is_required=False),
        "raw_measurements_table": AssetOut(key=AssetKey(["raw", "measurements"]), is_required=False),
    },
    group_name="ingestion",
    compute_kind="duckdb",
    deps=[raw_locations, raw_measurements],
    can_subset=False,
)
def raw_schema_loaded(context: AssetExecutionContext):
    """
    Load bronze Parquet into the DuckDB `raw` schema (full refresh).

    This is a @multi_asset rather than two separate @asset functions because
    `load_all()` genuinely loads both tables together in one call -- but it
    still needs to present as *two* distinct assets, keyed exactly
    `raw/locations` and `raw/measurements`, because those are the asset keys
    dagster-dbt automatically expects to satisfy stg_openaq__locations' and
    stg_openaq__measurements' `{{ source('raw', ...) }}` references. Get the
    keys wrong here and dbt's staging models will show up in Dagster's UI as
    having no upstream dependency at all.
    """
    results = load_all(mode="full")
    context.log.info("Loaded raw schema: %s", results)
    yield MaterializeResult(
        asset_key=AssetKey(["raw", "locations"]), metadata={"row_count": results["locations"]}
    )
    yield MaterializeResult(
        asset_key=AssetKey(["raw", "measurements"]), metadata={"row_count": results["measurements"]}
    )
