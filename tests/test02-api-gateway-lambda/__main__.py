import pulumi

from grocer_pulumi_components import ApiGatewayLambda

TAGS = {"project": "grocer-tests", "test": "test02", "managed-by": "pulumi"}

LAMBDA_CODE = """\
import json
import time

def handler(event, context):
    time.sleep(7)
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "done", "slept_seconds": 7}),
    }
"""

api = ApiGatewayLambda(
    "grocer-test02",
    handler="index.handler",
    runtime="python3.12",
    code=pulumi.AssetArchive({
        "index.py": pulumi.StringAsset(LAMBDA_CODE),
    }),
    route_key="GET /sleep",
    timeout=30,
    tags=TAGS,
)

pulumi.export("endpoint_url", api.endpoint_url)
pulumi.export("log_group_name", api.log_group_name)
