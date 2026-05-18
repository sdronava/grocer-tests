"""
Shared fixtures for the ec2-incident test suite.

Session-scoped fixtures load stack outputs and wait for SSM readiness once,
then share the results across all three test modules.

Setup order (automatic):
  1. ssm_ready  — blocks until the SSM agent is online (autouse, session-scoped)
  2. test_01_ssm.py  — verify SSM command execution
  3. test_02_alarm.py — spike CPU, wait for CloudWatch ALARM
  4. test_03_incident.py — verify PagerDuty incident, resolve it
"""

import json
import os
import subprocess
import time
from pathlib import Path

import boto3
import pytest

REGION = "us-east-1"
PULUMI_DIR = Path(__file__).parent.parent


def _stack_outputs(show_secrets: bool = False) -> dict:
    cmd = ["pulumi", "stack", "output", "--json"]
    if show_secrets:
        cmd.append("--show-secrets")
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=PULUMI_DIR)
    return json.loads(result.stdout)


@pytest.fixture(scope="session")
def outputs():
    return _stack_outputs()


@pytest.fixture(scope="session")
def secrets():
    return _stack_outputs(show_secrets=True)


@pytest.fixture(scope="session")
def instance_id(outputs):
    return outputs["instance_id"]


@pytest.fixture(scope="session")
def alarm_name(outputs):
    return outputs["alarm_name"]


@pytest.fixture(scope="session")
def sns_topic_arn(outputs):
    return outputs["sns_topic_arn"]


@pytest.fixture(scope="session")
def pd_service_id(outputs):
    return outputs["pd_service_id"]


@pytest.fixture(scope="session")
def pd_token():
    token = os.environ.get("PAGERDUTY_TOKEN")
    if not token:
        pytest.fail(
            "PAGERDUTY_TOKEN not set.\n"
            "  export PAGERDUTY_TOKEN=$(pulumi config get pagerduty:token)"
        )
    return token


@pytest.fixture(scope="session")
def ssm(instance_id):
    return boto3.client("ssm", region_name=REGION)


@pytest.fixture(scope="session")
def cw():
    return boto3.client("cloudwatch", region_name=REGION)


@pytest.fixture(scope="session", autouse=True)
def ssm_ready(instance_id, ssm):
    """Gate all tests — waits for SSM agent to register before any test runs."""
    timeout = 300
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = ssm.describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
        )
        if resp["InstanceInformationList"]:
            info = resp["InstanceInformationList"][0]
            print(f"\n✓ SSM agent online — version {info['AgentVersion']} on {instance_id}")
            return
        elapsed = int(timeout - (deadline - time.time()))
        print(f"\n  Waiting for SSM agent... ({elapsed}s / {timeout}s)")
        time.sleep(15)
    pytest.fail(f"SSM agent did not come online within {timeout}s")
