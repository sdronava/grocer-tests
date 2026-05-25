"""
Test 2 — No invocations for 5 minutes should trigger the heartbeat alarm.

Sends no requests. Polls until the alarm transitions to ALARM state
(treat_missing_data=breaching: an empty 5-minute window counts as a breach).
"""

import time

MAX_WAIT = 240   # 4 minutes — one 120s period + ~2 min processing buffer
POLL_INTERVAL = 20


def test_no_invocations_triggers_alarm(alarm_name, cw):
    print(f"\nNo requests will be sent. Polling for ALARM state (max {MAX_WAIT}s)...")

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
        f"Expected alarm to reach ALARM after 5 minutes of silence, "
        f"got {state} after {MAX_WAIT}s"
    )
    print(f"✓ Alarm state: ALARM (no invocations in last 5 min)")
