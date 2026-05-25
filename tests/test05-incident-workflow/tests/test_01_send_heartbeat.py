"""
Test 1 — Sending a heartbeat request should put the alarm in OK state.
"""
import time
import requests

MAX_WAIT = 240
POLL_INTERVAL = 20


def test_heartbeat_puts_alarm_ok(endpoint_url, alarm_name, cw):
    resp = requests.get(f"{endpoint_url}?sleep=3", timeout=15)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    print(f"\nHeartbeat sent. Polling for OK state (max {MAX_WAIT}s)...")

    deadline = time.time() + MAX_WAIT
    state = None
    while time.time() < deadline:
        state = cw.describe_alarms(AlarmNames=[alarm_name])["MetricAlarms"][0]["StateValue"]
        if state == "OK":
            break
        print(f"  Alarm state: {state} — waiting {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)

    assert state == "OK", f"Expected OK after heartbeat, got {state} after {MAX_WAIT}s"
    print("✓ Alarm state: OK")
