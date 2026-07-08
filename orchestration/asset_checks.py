"""
Dagster asset checks for operational concerns that don't belong in dbt
tests. dbt tests (run as part of `dbt build`) check data *correctness* --
uniqueness, referential integrity, valid ranges. This check is about
operational *freshness* -- "is the pipeline actually keeping up" -- which is
squarely an orchestration concern, not a transformation-layer one.
"""

from datetime import datetime, timedelta, timezone

from dagster import AssetCheckResult, AssetCheckSeverity, AssetKey, asset_check

from warehouse.db import get_connection


@asset_check(
    asset=AssetKey(["raw", "measurements"]),
    description="Warns if the newest measurement in raw.measurements is older than 48 hours",
)
def measurements_are_fresh() -> AssetCheckResult:
    conn = get_connection(read_only=True)
    try:
        latest = conn.execute(
            'SELECT MAX(try_cast("period__datetimeFrom__utc" as timestamp)) FROM raw.measurements'
        ).fetchone()[0]
    finally:
        conn.close()

    if latest is None:
        return AssetCheckResult(passed=False, description="raw.measurements has no rows yet")

    age = datetime.now(timezone.utc) - latest.replace(tzinfo=timezone.utc)
    passed = age <= timedelta(hours=48)
    return AssetCheckResult(
        passed=passed,
        severity=AssetCheckSeverity.WARN,
        metadata={
            "latest_reading_utc": str(latest),
            "age_hours": round(age.total_seconds() / 3600, 1),
        },
    )
