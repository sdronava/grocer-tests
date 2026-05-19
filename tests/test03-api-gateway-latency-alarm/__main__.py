import pulumi

from grocer_pulumi_components import ApiGatewayLambda
from grocer_pulumi_resources import GrocerMetricFilter, GrocerMetricAlarm

config = pulumi.Config()
alarm_source_ip = config.require("alarm_source_ip")

TAGS = {"project": "grocer-tests", "test": "test03", "managed-by": "pulumi"}
NAMESPACE = "grocer/ApiGateway/test03"

LAMBDA_CODE = """\
import json
import time

def handler(event, context):
    params = event.get("queryStringParameters") or {}
    sleep_secs = int(params.get("sleep", "7"))
    time.sleep(sleep_secs)
    return {
        "statusCode": 200,
        "body": json.dumps({"slept_seconds": sleep_secs}),
    }
"""

api = ApiGatewayLambda(
    "grocer-test03",
    handler="index.handler",
    runtime="python3.12",
    code=pulumi.AssetArchive({"index.py": pulumi.StringAsset(LAMBDA_CODE)}),
    route_key="GET /sleep",
    timeout=30,
    tags=TAGS,
)

GrocerMetricFilter(
    "grocer-test03",
    log_group_name=api.log_group_name,
    filter_pattern='{ $.sourceIp = "*" }',
    metric_name="IntegrationLatency",
    namespace=NAMESPACE,
    metric_value="$.integrationLatency",
    unit="Milliseconds",
    dimensions={"SourceIp": "$.sourceIp"},
)

alarm = GrocerMetricAlarm(
    "grocer-test03-latency",
    metric_name="IntegrationLatency",
    namespace=NAMESPACE,
    dimensions={"SourceIp": alarm_source_ip},
    alarm_actions=[],
    ok_actions=[],
    threshold=10000,
    period=60,
    evaluation_periods=1,
    statistic="Maximum",
    comparison_operator="GreaterThanThreshold",
    tags=TAGS,
)

pulumi.export("endpoint_url", api.endpoint_url)
pulumi.export("log_group_name", api.log_group_name)
pulumi.export("alarm_name", alarm.name)
pulumi.export("alarm_source_ip", alarm_source_ip)
