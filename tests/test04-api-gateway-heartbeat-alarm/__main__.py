import pulumi

from grocer_pulumi_components import ApiGatewayLambda, PagerDutyService
from grocer_pulumi_resources import (
    GrocerSnsTopic, GrocerSnsSubscription,
    GrocerMetricFilter, GrocerMetricAlarm,
)

config = pulumi.Config()
alarm_source_ip = config.require("alarm_source_ip")
pd_user_id = config.require("pd_escalation_target_user_id")

TAGS = {"project": "grocer-tests", "test": "test04", "managed-by": "pulumi"}
NAMESPACE = "grocer/ApiGateway/test04"

LAMBDA_CODE = """\
import json
import time

def handler(event, context):
    params = event.get("queryStringParameters") or {}
    sleep_secs = min(int(params.get("sleep", "3")), 5)
    time.sleep(sleep_secs)
    return {
        "statusCode": 200,
        "body": json.dumps({"slept_seconds": sleep_secs}),
    }
"""

api = ApiGatewayLambda(
    "grocer-test04",
    handler="index.handler",
    runtime="python3.12",
    code=pulumi.AssetArchive({"index.py": pulumi.StringAsset(LAMBDA_CODE)}),
    route_key="GET /invoke",
    timeout=10,
    tags=TAGS,
)

pd = PagerDutyService("grocer-test04", user_id=pd_user_id)

topic = GrocerSnsTopic("grocer-test04", tags=TAGS)

GrocerSnsSubscription(
    "grocer-test04",
    topic_arn=topic.arn,
    protocol="https",
    endpoint=pd.integration_key.apply(
        lambda key: f"https://events.pagerduty.com/adapter/cloudwatch_sns/v1/{key}"
    ),
)

# Emit RequestCount=1 per request, with SourceIp as a dimension.
GrocerMetricFilter(
    "grocer-test04",
    log_group_name=api.log_group_name,
    filter_pattern='{ $.sourceIp = "*" }',
    metric_name="RequestCount",
    namespace=NAMESPACE,
    metric_value="1",
    unit="Count",
    dimensions={"SourceIp": "$.sourceIp"},
)

# Alarm fires when Sum(RequestCount) < 1 over a 2-minute window —
# i.e., no invocations from the watched IP.
# treat_missing_data=breaching: an empty window counts as a breach.
alarm = GrocerMetricAlarm(
    "grocer-test04-heartbeat",
    metric_name="RequestCount",
    namespace=NAMESPACE,
    dimensions={"SourceIp": alarm_source_ip},
    alarm_actions=[topic.arn],
    ok_actions=[topic.arn],
    threshold=1,
    period=120,
    evaluation_periods=1,
    statistic="Sum",
    comparison_operator="LessThanThreshold",
    treat_missing_data="breaching",
    tags=TAGS,
)

pulumi.export("endpoint_url", api.endpoint_url)
pulumi.export("log_group_name", api.log_group_name)
pulumi.export("alarm_name", alarm.name)
pulumi.export("alarm_source_ip", alarm_source_ip)
pulumi.export("sns_topic_arn", topic.arn)
pulumi.export("pd_service_id", pd.service_id)
