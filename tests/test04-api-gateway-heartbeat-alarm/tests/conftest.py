import json
import os
import subprocess
from pathlib import Path

import boto3
import pytest

PULUMI_DIR = Path(__file__).parent.parent


@pytest.fixture(scope="session")
def outputs():
    result = subprocess.run(
        ["pulumi", "stack", "output", "--json"],
        capture_output=True, text=True, check=True, cwd=PULUMI_DIR,
    )
    return json.loads(result.stdout)


@pytest.fixture(scope="session")
def endpoint_url(outputs):
    return outputs["endpoint_url"]


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
def pd_token():
    token = os.environ.get("PAGERDUTY_TOKEN")
    if not token:
        pytest.skip("PAGERDUTY_TOKEN env var not set")
    return token


@pytest.fixture(scope="session")
def cw():
    return boto3.client("cloudwatch", region_name="us-east-1")
