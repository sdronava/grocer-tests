"""
Test 2 — Stopping heartbeats should trigger the alarm and create a PagerDuty incident.

No requests are sent. The 2-minute window empties, treat_missing_data=breaching fires
the alarm, SNS delivers to PagerDuty, and a triggered incident appears on the service.
"""
import time
import requests

MAX_WAIT_ALARM    = 600
MAX_WAIT_INCIDENT = 120
POLL_INTERVAL     = 20
PD_API = "https://api.pagerduty.com"


def test_no_heartbeat_triggers_alarm(alarm_name, cw):
    print(f"\nNo requests will be sent. Polling for ALARM state (max {MAX_WAIT_ALARM}s)...")
    deadline = time.time() + MAX_WAIT_ALARM
    state = None
    while time.time() < deadline:
        state = cw.describe_alarms(AlarmNames=[alarm_name])["MetricAlarms"][0]["StateValue"]
        if state == "ALARM":
            break
        print(f"  Alarm state: {state} — waiting {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)

    assert state == "ALARM", f"Expected ALARM after missing heartbeat, got {state} after {MAX_WAIT_ALARM}s"
    print("✓ Alarm state: ALARM")


def test_pagerduty_incident_triggered(pd_service_id, pd_headers):
    print(f"\nPolling PagerDuty for triggered incident on service {pd_service_id} (max {MAX_WAIT_INCIDENT}s)...")
    deadline = time.time() + MAX_WAIT_INCIDENT
    while time.time() < deadline:
        resp = requests.get(
            f"{PD_API}/incidents",
            headers=pd_headers,
            params={"service_ids[]": pd_service_id, "statuses[]": "triggered"},
        )
        assert resp.status_code == 200, f"PD API error: {resp.status_code} {resp.text}"
        if resp.json().get("incidents"):
            print(f"✓ PagerDuty incident triggered: {resp.json()['incidents'][0]['id']}")
            return
        time.sleep(POLL_INTERVAL)

    raise AssertionError(f"No triggered PagerDuty incident found within {MAX_WAIT_INCIDENT}s")
