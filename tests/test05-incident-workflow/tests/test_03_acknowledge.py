"""
Test 3 — Acknowledge the incident, which triggers the PagerDuty webhook
         and fires the workflow Lambda (Jira + Google Meet + Slack).

Stores the incident ID in a module-level variable so subsequent tests can reference it.
"""
import time
import requests
import pytest

PD_API = "https://api.pagerduty.com"
MAX_WAIT      = 60
POLL_INTERVAL = 10

# Shared across tests in this session via module-level state.
# pytest does not support cross-test fixtures with mutable state neatly,
# so we write to a known location via a session-scoped fixture instead.
acknowledged_incident_id = None


def test_acknowledge_incident(pd_service_id, pd_headers, request):
    global acknowledged_incident_id

    resp = requests.get(
        f"{PD_API}/incidents",
        headers=pd_headers,
        params={"service_ids[]": pd_service_id, "statuses[]": "triggered"},
    )
    assert resp.status_code == 200
    incidents = resp.json().get("incidents", [])
    assert incidents, "No triggered incident found — run test_02 first"

    incident_id = incidents[0]["id"]
    print(f"\nAcknowledging incident {incident_id}...")

    ack = requests.put(
        f"{PD_API}/incidents/{incident_id}",
        headers=pd_headers,
        json={"incident": {"type": "incident_reference", "status": "acknowledged"}},
    )
    assert ack.status_code == 200, f"Failed to acknowledge: {ack.status_code} {ack.text}"

    acknowledged_incident_id = incident_id
    print(f"✓ Incident {incident_id} acknowledged")
    print("  Webhook will fire the workflow Lambda asynchronously.")
    print("  Allowing 30s for Lambda to complete before verifying side effects...")
    time.sleep(30)
