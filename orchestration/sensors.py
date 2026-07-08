"""
Fires whenever any run of the pipeline job fails, regardless of which asset
caused it. Logged here rather than wired to a real Slack webhook, since a
portfolio project's demonstrability shouldn't depend on a live webhook
secret existing -- but the production version of this is genuinely just a
few added lines, shown in the comment below.
"""

from dagster import RunFailureSensorContext, run_failure_sensor


@run_failure_sensor
def pipeline_failure_sensor(context: RunFailureSensorContext) -> None:
    context.log.error(
        "AirPulse pipeline run %s failed: %s",
        context.dagster_run.run_id,
        context.failure_event.message,
    )
    # Production hook -- left as a comment rather than a hard dependency on
    # a real secret:
    #
    # import requests
    # requests.post(
    #     SLACK_WEBHOOK_URL,
    #     json={"text": f"AirPulse pipeline failed: {context.failure_event.message}"},
    # )
