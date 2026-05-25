"""
Test 3 — PagerDuty incident lifecycle.

Verifies SNS delivered to PagerDuty without failures, waits for a triggered
incident, resolves it, and confirms the resolved state.
"""

import time
from datetime import datetime, timedelta, timezone

import boto3
import pytest
import requests

REGION = "us-east-1"
PD_API = "https://api.pagerduty.com"


def _pd_headers(token: str) -> dict:
    return {
        "Authorization": f"Token token={token}",
        "Accept": "application/vnd.pagerduty+json;version=2",
        "Content-Type": "application/json",
    }


def test_sns_no_delivery_failures(sns_topic_arn, cw):
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
    assert failed == 0, f"{int(failed)} SNS notification(s) failed to deliver"
    print("\n✓ SNS delivery: no failures")


def test_pagerduty_incident_triggered_and_resolved(pd_service_id, pd_token):
    headers = _pd_headers(pd_token)

    # Wait for triggered incident
    deadline = time.time() + 180
    incident = None
    while time.time() < deadline:
        resp = requests.get(
            f"{PD_API}/incidents",
            headers=headers,
            params={"service_ids[]": pd_service_id, "statuses[]": "triggered"},
        )
        resp.raise_for_status()
        incidents = resp.json().get("incidents", [])
        if incidents:
            incident = incidents[0]
            print(f"\n✓ Incident triggered: {incident['id']} — {incident['title']}")
            break
        print("\n  Waiting for triggered incident...")
        time.sleep(10)

    if not incident:
        pytest.fail("No triggered incident found within 180s")

    # Resolve
    resp = requests.put(
        f"{PD_API}/incidents/{incident['id']}",
        headers=headers,
        json={"incident": {"type": "incident_reference", "status": "resolved"}},
    )
    resp.raise_for_status()
    print(f"  Resolve request sent for {incident['id']}")

    # Confirm resolved
    deadline = time.time() + 60
    while time.time() < deadline:
        resp = requests.get(f"{PD_API}/incidents/{incident['id']}", headers=headers)
        resp.raise_for_status()
        status = resp.json()["incident"]["status"]
        print(f"  Incident status: {status}")
        if status == "resolved":
            print(f"✓ Incident {incident['id']} resolved")
            return
        time.sleep(10)

    pytest.fail(f"Incident {incident['id']} not resolved within 60s")
