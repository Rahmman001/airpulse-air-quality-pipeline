"""
The entire dbt project -- staging, intermediate, marts, and the SCD2
snapshot -- as Dagster software-defined assets, generated directly from
dbt's manifest.json. Dagster's lineage graph is therefore always an exact
mirror of dbt's real `ref()` dependencies; there is no manually-maintained
asset list to drift out of sync with the dbt project.

The one design decision that matters here: this runs `dbt build`, not
`dbt run`. `dbt run` does not execute snapshots -- which is exactly why
Phase 3's README documents a manual three-step sequence
(`dbt run --select staging` -> `dbt snapshot` -> `dbt run`). `dbt build`
runs models, snapshots, and tests together in dependency order, so Dagster
resolves that ordering for you automatically. This is the concrete payoff
of introducing a real orchestrator instead of a person having to remember
a manual run order.
"""

from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets

from orchestration.project import airpulse_dbt_project


@dbt_assets(manifest=airpulse_dbt_project.manifest_path)
def airpulse_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()
