"""
Test 3 — Alarm should recover to OK automatically after the slow request.

With treat_missing_data=notBreaching and period=60, one empty evaluation window
is enough to return the alarm to OK. No additional requests are sent.
"""

import time

POLL_INTERVAL = 15  # seconds between alarm state checks
MAX_WAIT = 300      # seconds to wait for recovery — up to 2 full 60s evaluation periods


def test_alarm_recovers_to_ok(alarm_name, cw):
    print(f"\nPolling for alarm recovery to OK (max {MAX_WAIT}s)...")

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
        f"Expected alarm to recover to OK within {MAX_WAIT}s, but final state was: {state}"
    )
    print(f"✓ Alarm recovered to OK")
