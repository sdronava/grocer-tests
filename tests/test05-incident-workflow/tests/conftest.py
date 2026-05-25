import json
import os
import subprocess
from pathlib import Path

import boto3
import pytest
import requests

PULUMI_DIR = Path(__file__).parent.parent
PD_API = "https://api.pagerduty.com"


@pytest.fixture(scope="session")
def outputs():
    result = subprocess.run(
        ["pulumi", "stack", "output", "--json"],
        capture_output=True, text=True, check=True, cwd=PULUMI_DIR,
    )
    return json.loads(result.stdout)


@pytest.fixture(scope="session")
def endpoint_url(outputs):
    return outputs["heartbeat_endpoint_url"]


@pytest.fixture(scope="session")
def alarm_name(outputs):
    return outputs["alarm_name"]


@pytest.fixture(scope="session")
def alarm_source_ip(outputs):
    return outputs["alarm_source_ip"]


@pytest.fixture(scope="session")
def pd_service_id(outputs):
    return outputs["pd_service_id"]


@pytest.fixture(scope="session")
def jira_site_url(outputs):
    return outputs["jira_site_url"]


@pytest.fixture(scope="session")
def jira_project_key(outputs):
    return outputs["jira_project_key"]


@pytest.fixture(scope="session")
def slack_incidents_channel_id(outputs):
    return outputs["slack_incidents_channel_id"]


@pytest.fixture(scope="session")
def pd_token():
    token = os.environ.get("PAGERDUTY_TOKEN")
    if not token:
        pytest.skip("PAGERDUTY_TOKEN env var not set")
    return token


@pytest.fixture(scope="session")
def slack_bot_token():
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        pytest.skip("SLACK_BOT_TOKEN env var not set")
    return token


@pytest.fixture(scope="session")
def jira_auth():
    email = os.environ.get("JIRA_USER_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")
    if not email or not token:
        pytest.skip("JIRA_USER_EMAIL or JIRA_API_TOKEN env var not set")
    return (email, token)


@pytest.fixture(scope="session")
def cw():
    return boto3.client("cloudwatch", region_name="us-east-1")


@pytest.fixture(scope="session")
def pd_headers(pd_token):
    return {
        "Authorization": f"Token token={pd_token}",
        "Accept": "application/vnd.pagerduty+json;version=2",
        "Content-Type": "application/json",
        "From": "srinath.dv@gmail.com",
    }
