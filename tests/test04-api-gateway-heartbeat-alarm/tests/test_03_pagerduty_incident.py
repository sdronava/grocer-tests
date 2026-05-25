"""
Test 3 — Alarm firing should trigger a PagerDuty incident via SNS.

Polls the PagerDuty REST API for a triggered incident on the service,
then resolves it so subsequent test runs start clean.
"""

import time

import requests

PD_API = "https://api.pagerduty.com"
MAX_WAIT = 120   # seconds to poll PD for the incident
POLL_INTERVAL = 10


def test_pagerduty_incident_triggered_and_resolved(alarm_name, pd_service_id, pd_token, cw):
    # Confirm the alarm is still in ALARM before checking PD.
    result = cw.describe_alarms(AlarmNames=[alarm_name])
    state = result["MetricAlarms"][0]["StateValue"]
    assert state == "ALARM", f"Expected alarm to be in ALARM state, got {state}"

    headers = {
        "Authorization": f"Token token={pd_token}",
        "Accept": "application/vnd.pagerduty+json;version=2",
    }

    print(f"\nPolling PagerDuty for triggered incident on service {pd_service_id} (max {MAX_WAIT}s)...")
    deadline = time.time() + MAX_WAIT
    incident_id = None
    while time.time() < deadline:
        resp = requests.get(
            f"{PD_API}/incidents",
            headers=headers,
            params={"service_ids[]": pd_service_id, "statuses[]": "triggered"},
        )
        assert resp.status_code == 200, f"PD API error: {resp.status_code} {resp.text}"
        incidents = resp.json().get("incidents", [])
        if incidents:
            incident_id = incidents[0]["id"]
            break
        time.sleep(POLL_INTERVAL)

    assert incident_id, (
        f"No triggered PagerDuty incident found for service {pd_service_id} within {MAX_WAIT}s"
    )
    print(f"  Found incident {incident_id} — resolving...")

    resp = requests.put(
        f"{PD_API}/incidents/{incident_id}",
        headers={**headers, "From": "srinath.dv@gmail.com"},
        json={"incident": {"type": "incident_reference", "status": "resolved"}},
    )
    assert resp.status_code == 200, f"Failed to resolve incident: {resp.status_code} {resp.text}"
    print(f"✓ PagerDuty incident {incident_id} triggered and resolved")
