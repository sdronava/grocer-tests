"""
Test 4 — Sending a request after the alarm fires should recover it to OK.

Sends GET /invoke?sleep=3, then polls until the alarm returns to OK.
The SNS ok_action also sends a resolve notification to PagerDuty.
"""

import time

import requests

SLEEP_SECS = 3
MAX_WAIT = 240   # 4 minutes — one 120s period + ~2 min processing buffer
POLL_INTERVAL = 20


def test_send_request_recovers_alarm(endpoint_url, alarm_name, cw):
    resp = requests.get(f"{endpoint_url}?sleep={SLEEP_SECS}", timeout=15)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert body["slept_seconds"] == SLEEP_SECS, f"Unexpected body: {body}"
    print(f"\nRequest completed ({SLEEP_SECS}s). Polling for OK state (max {MAX_WAIT}s)...")

    deadline = time.time() + MAX_WAIT
    state = None
    while time.time() < deadline:
        result = cw.describe_alarms(AlarmNames=[alarm_name])
        state = result["MetricAlarms"][0]["StateValue"]
        if state == "OK":
            break
        print(f"  Alarm state: {state} — waiting {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)

    assert state == "OK", (
        f"Expected alarm to recover to OK after resuming invocations, "
        f"got {state} after {MAX_WAIT}s"
    )
    print(f"✓ Alarm recovered to OK")
