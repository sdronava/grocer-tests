"""
Test 1 — Fast request (5s) should NOT trigger the latency alarm (threshold: 10s).

Sends GET /sleep?sleep=5, then waits for CloudWatch to evaluate and asserts the
alarm remains OK or INSUFFICIENT_DATA.
"""

import time

import requests

SLEEP_SECS = 5
ALARM_EVAL_WAIT = 90  # seconds — log processing (~30s) + one alarm period (60s)


def test_fast_request_no_alarm(endpoint_url, alarm_name, cw):
    resp = requests.get(f"{endpoint_url}?sleep={SLEEP_SECS}", timeout=30)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert body["slept_seconds"] == SLEEP_SECS, f"Unexpected body: {body}"

    print(f"\nRequest completed in ~{SLEEP_SECS}s. Waiting {ALARM_EVAL_WAIT}s for alarm evaluation...")
    time.sleep(ALARM_EVAL_WAIT)

    result = cw.describe_alarms(AlarmNames=[alarm_name])
    alarms = result["MetricAlarms"]
    assert alarms, f"Alarm '{alarm_name}' not found"

    state = alarms[0]["StateValue"]
    assert state in ("OK", "INSUFFICIENT_DATA"), (
        f"Expected OK or INSUFFICIENT_DATA after a {SLEEP_SECS}s request, got {state}"
    )
    print(f"✓ Alarm state after fast request: {state}")
