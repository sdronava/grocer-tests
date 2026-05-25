import pulumi
import pulumi_pagerduty as pagerduty

from grocer_pulumi_components import ApiGatewayLambda, PagerDutyService
from grocer_pulumi_resources import (
    GrocerIamRole, GrocerLambdaFunction, GrocerLambdaPermission,
    GrocerHttpApi, GrocerHttpApiIntegration, GrocerHttpApiRoute, GrocerHttpApiStage,
    GrocerSnsTopic, GrocerSnsSubscription,
    GrocerMetricFilter, GrocerMetricAlarm,
)

config = pulumi.Config()

alarm_source_ip         = config.require("alarm_source_ip")
pd_user_id              = config.require("pd_escalation_target_user_id")
jira_site_url           = config.require("jira_site_url").rstrip("/")
jira_project_key        = config.require("jira_project_key")
jira_issue_type         = config.require("jira_issue_type")
slack_incidents_channel = config.require("slack_incidents_channel_id")
oncall_slack_user_ids   = config.require("oncall_slack_user_ids")
google_calendar_id      = config.require("google_calendar_id")

jira_user_email          = config.require_secret("jira_user_email")
jira_api_token           = config.require_secret("jira_api_token")
slack_bot_token          = config.require_secret("slack_bot_token")
slack_signing_secret     = config.require_secret("slack_signing_secret")
google_service_account_key = config.require_secret("google_service_account_key")

TAGS = {"project": "grocer-tests", "test": "test05", "managed-by": "pulumi"}
NAMESPACE = "grocer/ApiGateway/test05"

# ---------------------------------------------------------------------------
# Heartbeat Lambda + API Gateway (same pattern as test04)
# ---------------------------------------------------------------------------
HEARTBEAT_CODE = """\
import json, time

def handler(event, context):
    params = (event.get("queryStringParameters") or {})
    sleep_secs = min(int(params.get("sleep", "3")), 5)
    time.sleep(sleep_secs)
    return {"statusCode": 200, "body": json.dumps({"slept_seconds": sleep_secs})}
"""

heartbeat = ApiGatewayLambda(
    "grocer-test05-heartbeat",
    handler="index.handler",
    runtime="python3.12",
    code=pulumi.AssetArchive({"index.py": pulumi.StringAsset(HEARTBEAT_CODE)}),
    route_key="GET /invoke",
    timeout=10,
    tags=TAGS,
)

# ---------------------------------------------------------------------------
# CloudWatch metric filter + heartbeat alarm  (no ok_actions — no auto-resolve)
# ---------------------------------------------------------------------------
GrocerMetricFilter(
    "grocer-test05",
    log_group_name=heartbeat.log_group_name,
    filter_pattern='{ $.sourceIp = "*" }',
    metric_name="RequestCount",
    namespace=NAMESPACE,
    metric_value="1",
    unit="Count",
    dimensions={"SourceIp": "$.sourceIp"},
)

# SNS + PagerDuty must exist before alarm can reference topic.arn
pd = PagerDutyService("grocer-test05", user_id=pd_user_id)
topic = GrocerSnsTopic("grocer-test05", tags=TAGS)
GrocerSnsSubscription(
    "grocer-test05",
    topic_arn=topic.arn,
    protocol="https",
    endpoint=pd.integration_key.apply(
        lambda key: f"https://events.pagerduty.com/adapter/cloudwatch_sns/v1/{key}"
    ),
)

alarm = GrocerMetricAlarm(
    "grocer-test05-heartbeat",
    metric_name="RequestCount",
    namespace=NAMESPACE,
    dimensions={"SourceIp": alarm_source_ip},
    alarm_actions=[topic.arn],
    ok_actions=[],
    threshold=1,
    period=120,
    evaluation_periods=1,
    statistic="Sum",
    comparison_operator="LessThanThreshold",
    treat_missing_data="breaching",
    tags=TAGS,
)

# ---------------------------------------------------------------------------
# Workflow Lambda — called by PagerDuty webhook on incident.acknowledged
# Creates a Jira ticket, a Google Meet event, and posts a Slack Block Kit message.
# Run ./build.sh before pulumi up to install Lambda dependencies.
# ---------------------------------------------------------------------------
workflow_role = GrocerIamRole(
    "grocer-test05-workflow",
    trust_service="lambda.amazonaws.com",
    policy_arns=["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"],
    tags=TAGS,
)

workflow_env = pulumi.Output.all(
    jira_user_email=jira_user_email,
    jira_api_token=jira_api_token,
    slack_bot_token=slack_bot_token,
    google_service_account_key=google_service_account_key,
).apply(lambda s: {
    "JIRA_SITE_URL":               jira_site_url,
    "JIRA_PROJECT_KEY":            jira_project_key,
    "JIRA_ISSUE_TYPE":             jira_issue_type,
    "SLACK_INCIDENTS_CHANNEL_ID":  slack_incidents_channel,
    "GOOGLE_CALENDAR_ID":          google_calendar_id,
    "JIRA_USER_EMAIL":             s["jira_user_email"],
    "JIRA_API_TOKEN":              s["jira_api_token"],
    "SLACK_BOT_TOKEN":             s["slack_bot_token"],
    "GOOGLE_SERVICE_ACCOUNT_KEY":  s["google_service_account_key"],
})

workflow_fn = GrocerLambdaFunction(
    "grocer-test05-workflow",
    handler="handler.handler",
    runtime="python3.12",
    code=pulumi.FileArchive("lambdas/workflow/dist/"),
    role_arn=workflow_role.arn,
    timeout=30,
    environment=workflow_env,
    tags=TAGS,
)

workflow_api   = GrocerHttpApi("grocer-test05-workflow", tags=TAGS)
workflow_integ = GrocerHttpApiIntegration(
    "grocer-test05-workflow",
    api_id=workflow_api.id,
    integration_uri=workflow_fn.invoke_arn,
)
GrocerHttpApiRoute(
    "grocer-test05-workflow",
    api_id=workflow_api.id,
    route_key="POST /webhook",
    integration_id=workflow_integ.id,
)
workflow_stage = GrocerHttpApiStage("grocer-test05-workflow", api_id=workflow_api.id, tags=TAGS)
GrocerLambdaPermission(
    "grocer-test05-workflow",
    function_name=workflow_fn.name,
    principal="apigateway.amazonaws.com",
    source_arn=workflow_api.execution_arn.apply(lambda arn: f"{arn}/*/*"),
)
workflow_url = workflow_stage.invoke_url.apply(lambda u: u.rstrip("/") + "/webhook")

# ---------------------------------------------------------------------------
# Slack interactivity Lambda — handles "Create War Room" button clicks
# Post-deploy: paste slack_interactivity_url into the Slack App's Request URL
#              (see SLACK_APP_SETUP.md Step 5)
# ---------------------------------------------------------------------------
slack_role = GrocerIamRole(
    "grocer-test05-slack",
    trust_service="lambda.amazonaws.com",
    policy_arns=["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"],
    tags=TAGS,
)

slack_env = pulumi.Output.all(
    slack_bot_token=slack_bot_token,
    slack_signing_secret=slack_signing_secret,
).apply(lambda s: {
    "SLACK_BOT_TOKEN":       s["slack_bot_token"],
    "SLACK_SIGNING_SECRET":  s["slack_signing_secret"],
    "ONCALL_SLACK_USER_IDS": oncall_slack_user_ids,
})

slack_fn = GrocerLambdaFunction(
    "grocer-test05-slack",
    handler="handler.handler",
    runtime="python3.12",
    code=pulumi.FileArchive("slack_app/dist/"),
    role_arn=slack_role.arn,
    timeout=10,
    environment=slack_env,
    tags=TAGS,
)

slack_api   = GrocerHttpApi("grocer-test05-slack", tags=TAGS)
slack_integ = GrocerHttpApiIntegration(
    "grocer-test05-slack",
    api_id=slack_api.id,
    integration_uri=slack_fn.invoke_arn,
)
GrocerHttpApiRoute(
    "grocer-test05-slack",
    api_id=slack_api.id,
    route_key="POST /slack/interactivity",
    integration_id=slack_integ.id,
)
slack_stage = GrocerHttpApiStage("grocer-test05-slack", api_id=slack_api.id, tags=TAGS)
GrocerLambdaPermission(
    "grocer-test05-slack",
    function_name=slack_fn.name,
    principal="apigateway.amazonaws.com",
    source_arn=slack_api.execution_arn.apply(lambda arn: f"{arn}/*/*"),
)
slack_interactivity_url = slack_stage.invoke_url.apply(lambda u: u.rstrip("/") + "/slack/interactivity")

# ---------------------------------------------------------------------------
# PagerDuty V3 webhook — fires on incident.acknowledged for this service only
# ---------------------------------------------------------------------------
pagerduty.WebhookSubscription(
    "grocer-test05-webhook",
    delivery_methods=[pagerduty.WebhookSubscriptionDeliveryMethodArgs(
        type="http_delivery_method",
        url=workflow_url,
    )],
    events=["incident.acknowledged"],
    filters=[pagerduty.WebhookSubscriptionFilterArgs(
        type="service_reference",
        id=pd.service_id,
    )],
    active=True,
)

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------
pulumi.export("heartbeat_endpoint_url",  heartbeat.endpoint_url)
pulumi.export("heartbeat_log_group_name", heartbeat.log_group_name)
pulumi.export("alarm_name",              alarm.name)
pulumi.export("alarm_source_ip",         alarm_source_ip)
pulumi.export("sns_topic_arn",           topic.arn)
pulumi.export("pd_service_id",           pd.service_id)
pulumi.export("workflow_webhook_url",    workflow_url)
pulumi.export("slack_interactivity_url", slack_interactivity_url)
pulumi.export("jira_site_url",           jira_site_url)
pulumi.export("jira_project_key",        jira_project_key)
pulumi.export("slack_incidents_channel_id", slack_incidents_channel)
