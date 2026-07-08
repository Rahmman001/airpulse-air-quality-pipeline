"""
Schedule for the full pipeline: ingestion -> raw load -> dbt build.

Every 6 hours balances staying reasonably current against OpenAQ's 60
requests/minute rate limit and the fact that this is a portfolio project,
not a system with a real operational SLA. Tune freely -- this is a config
value, not a design commitment.
"""

from dagster import ScheduleDefinition, define_asset_job

airpulse_pipeline_job = define_asset_job(
    name="airpulse_pipeline_job",
    description="Full pipeline: pull from OpenAQ, load raw, build dbt models.",
)

airpulse_schedule = ScheduleDefinition(
    job=airpulse_pipeline_job,
    cron_schedule="0 */6 * * *",
    execution_timezone="UTC",
)
