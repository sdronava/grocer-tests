"""
Test 2 — CloudWatch alarm fires on CPU spike.

Sends stress-ng via SSM to breach the CPUUtilization threshold, then polls
CloudWatch until the alarm enters ALARM state (timeout: 6 min).
"""

import time

import pytest


def test_cpu_spike_triggers_alarm(instance_id, alarm_name, ssm, cw):
    resp = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [
            "dnf install -y stress-ng 2>/dev/null || true",
            "stress-ng --cpu 0 --timeout 180s &",
        ]},
    )
    print(f"\n  CPU spike command sent: {resp['Command']['CommandId']}")

    timeout = 360
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = cw.describe_alarms(AlarmNames=[alarm_name])
        alarms = resp.get("MetricAlarms", [])
        if alarms:
            state = alarms[0]["StateValue"]
            print(f"  Alarm state: {state}")
            if state == "ALARM":
                print(f"✓ Alarm '{alarm_name}' entered ALARM state")
                return
        time.sleep(15)

    pytest.fail(f"Alarm did not reach ALARM state within {timeout}s")
