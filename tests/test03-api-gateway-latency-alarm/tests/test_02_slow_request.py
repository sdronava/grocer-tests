"""
Test 2 — Slow request (12s) SHOULD trigger the latency alarm (threshold: 10s).

Sends GET /sleep?sleep=12, then polls CloudWatch up to 3 minutes for the alarm
to transition to ALARM state.
"""

import time

import requests

SLEEP_SECS = 12
POLL_INTERVAL = 15   # seconds between alarm state checks
MAX_WAIT = 180       # seconds to wait for ALARM state


def test_slow_request_triggers_alarm(endpoint_url, alarm_name, cw):
    resp = requests.get(f"{endpoint_url}?sleep={SLEEP_SECS}", timeout=30)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert body["slept_seconds"] == SLEEP_SECS, f"Unexpected body: {body}"

    print(f"\nRequest completed in ~{SLEEP_SECS}s. Polling for ALARM state (max {MAX_WAIT}s)...")

    deadline = time.time() + MAX_WAIT
    state = None
    while time.time() < deadline:
        result = cw.describe_alarms(AlarmNames=[alarm_name])
        state = result["MetricAlarms"][0]["StateValue"]
        if state == "ALARM":
            break
        print(f"  Alarm state: {state} — waiting {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)

    assert state == "ALARM", (
        f"Expected alarm to reach ALARM state within {MAX_WAIT}s after a {SLEEP_SECS}s request, "
        f"but final state was: {state}"
    )
    print(f"✓ Alarm transitioned to ALARM")
