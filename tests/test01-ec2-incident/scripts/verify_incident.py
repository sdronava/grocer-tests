"""
Verify the full alert pipeline after trigger_alarm.py has fired the alarm:
  1. Confirm SNS delivered to PagerDuty without failures
  2. Wait for a triggered incident on the PagerDuty service
  3. Resolve the incident via the PagerDuty REST API
  4. Confirm the incident reaches resolved state

Side-effects:
  - Resolves the PagerDuty incident created by the alarm

Run:
  uv run pytest scripts/verify_incident.py -v -s
  uv run python scripts/verify_incident.py
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
import requests

REGION = "us-east-1"
PD_REST_API = "https://api.pagerduty.com"
PULUMI_DIR = Path(__file__).parent.parent


def get_stack_outputs() -> dict:
    result = subprocess.run(
        ["pulumi", "stack", "output", "--json", "--show-secrets"],
        capture_output=True, text=True, check=True, cwd=PULUMI_DIR,
    )
    return json.loads(result.stdout)


def get_pd_token() -> str:
    token = os.environ.get("PAGERDUTY_TOKEN")
    if not token:
        print("✗ PAGERDUTY_TOKEN environment variable not set", file=sys.stderr)
        print("  export PAGERDUTY_TOKEN=$(pulumi config get pagerduty:token)", file=sys.stderr)
        sys.exit(1)
    return token


def pd_headers(token: str) -> dict:
    return {
        "Authorization": f"Token token={token}",
        "Accept": "application/vnd.pagerduty+json;version=2",
        "Content-Type": "application/json",
    }


def check_sns_delivery(sns_topic_arn: str) -> None:
    cw = boto3.client("cloudwatch", region_name=REGION)
    now = datetime.now(timezone.utc)
    resp = cw.get_metric_statistics(
        Namespace="AWS/SNS",
        MetricName="NumberOfNotificationsFailed",
        Dimensions=[{"Name": "TopicName", "Value": sns_topic_arn.split(":")[-1]}],
        StartTime=now - timedelta(minutes=15),
        EndTime=now,
        Period=900,
        Statistics=["Sum"],
    )
    failed = sum(dp["Sum"] for dp in resp.get("Datapoints", []))
    assert failed == 0, f"✗ {int(failed)} SNS notification(s) failed to deliver"
    print("✓ SNS delivery: no failures")


def wait_for_triggered_incident(service_id: str, token: str, timeout: int = 180) -> dict:
    headers = pd_headers(token)
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{PD_REST_API}/incidents",
            headers=headers,
            params={"service_ids[]": service_id, "statuses[]": "triggered"},
        )
        resp.raise_for_status()
        incidents = resp.json().get("incidents", [])
        if incidents:
            incident = incidents[0]
            print(f"✓ Incident triggered: {incident['id']} — {incident['title']}")
            return incident
        print("  Waiting for triggered incident...")
        time.sleep(10)
    print("✗ No triggered incident found within timeout", file=sys.stderr)
    sys.exit(1)


def resolve_incident(incident_id: str, token: str) -> None:
    headers = pd_headers(token)
    resp = requests.put(
        f"{PD_REST_API}/incidents/{incident_id}",
        headers=headers,
        json={"incident": {"type": "incident_reference", "status": "resolved"}},
    )
    resp.raise_for_status()
    print(f"  Resolve request sent for incident {incident_id}")


def wait_for_resolved(incident_id: str, token: str, timeout: int = 60) -> None:
    headers = pd_headers(token)
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{PD_REST_API}/incidents/{incident_id}", headers=headers)
        resp.raise_for_status()
        status = resp.json()["incident"]["status"]
        print(f"  Incident status: {status}")
        if status == "resolved":
            print(f"✓ Incident {incident_id} resolved")
            return
        time.sleep(10)
    print(f"✗ Incident {incident_id} not resolved within {timeout}s", file=sys.stderr)
    sys.exit(1)


def test_verify_incident():
    outputs = get_stack_outputs()
    sns_topic_arn = outputs["sns_topic_arn"]
    service_id = outputs["pd_service_id"]
    token = get_pd_token()

    print(f"\nSNS topic: {sns_topic_arn}")
    print(f"PD service: {service_id}")

    check_sns_delivery(sns_topic_arn)
    incident = wait_for_triggered_incident(service_id, token)
    resolve_incident(incident["id"], token)
    wait_for_resolved(incident["id"], token)


if __name__ == "__main__":
    test_verify_incident()
