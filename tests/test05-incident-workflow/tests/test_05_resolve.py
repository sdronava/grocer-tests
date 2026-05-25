"""
Test 5 — Manually resolve the incident via PagerDuty API.

The incident was not auto-resolved (no ok_actions on the alarm).
This test resolves it explicitly and confirms the final state.
"""
import time
import requests

PD_API        = "https://api.pagerduty.com"
MAX_WAIT      = 60
POLL_INTERVAL = 10


def test_resolve_incident(pd_service_id, pd_headers):
    resp = requests.get(
        f"{PD_API}/incidents",
        headers=pd_headers,
        params={"service_ids[]": pd_service_id, "statuses[]": "acknowledged"},
    )
    assert resp.status_code == 200
    incidents = resp.json().get("incidents", [])
    assert incidents, "No acknowledged incident found — run test_03 first"

    incident_id = incidents[0]["id"]
    print(f"\nResolving incident {incident_id}...")

    resp = requests.put(
        f"{PD_API}/incidents/{incident_id}",
        headers=pd_headers,
        json={"incident": {"type": "incident_reference", "status": "resolved"}},
    )
    assert resp.status_code == 200, f"Failed to resolve: {resp.status_code} {resp.text}"

    # Confirm the incident is now resolved.
    deadline = time.time() + MAX_WAIT
    status = None
    while time.time() < deadline:
        check = requests.get(f"{PD_API}/incidents/{incident_id}", headers=pd_headers)
        status = check.json()["incident"]["status"]
        if status == "resolved":
            break
        time.sleep(POLL_INTERVAL)

    assert status == "resolved", f"Expected resolved, got {status} after {MAX_WAIT}s"
    print(f"✓ Incident {incident_id} resolved")
    print("  Note: Jira ticket and Slack messages require manual cleanup.")
