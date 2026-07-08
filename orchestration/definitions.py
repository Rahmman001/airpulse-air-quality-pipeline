"""
The single Dagster Definitions object tying together every asset, resource,
schedule, sensor, and asset check in this project. This is what `dagster
dev` actually loads (see the [tool.dagster] entry in pyproject.toml /
the module_name pointed at by `dagster dev -m orchestration.definitions`).
"""

from dagster import Definitions

from orchestration.asset_checks import measurements_are_fresh
from orchestration.assets.dbt_assets import airpulse_dbt_assets
from orchestration.assets.ingestion_assets import raw_locations, raw_measurements, raw_schema_loaded
from orchestration.project import dbt_resource
from orchestration.schedules import airpulse_schedule
from orchestration.sensors import pipeline_failure_sensor

defs = Definitions(
    assets=[raw_locations, raw_measurements, raw_schema_loaded, airpulse_dbt_assets],
    asset_checks=[measurements_are_fresh],
    resources={"dbt": dbt_resource},
    schedules=[airpulse_schedule],
    sensors=[pipeline_failure_sensor],
)
