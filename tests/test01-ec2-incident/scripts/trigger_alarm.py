"""
Spike CPU on the test EC2 instance via SSM Run Command, then wait for the
CloudWatch alarm to enter ALARM state.

Side-effects:
  - Sends an SSM Run Command to the EC2 instance (runs stress-ng for 180s)
  - Polls CloudWatch every 15s until alarm state == ALARM (timeout: 6 min)

Run:
  uv run pytest scripts/trigger_alarm.py -v -s
  uv run python scripts/trigger_alarm.py
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import boto3

REGION = "us-east-1"
PULUMI_DIR = Path(__file__).parent.parent


def get_stack_outputs() -> dict:
    result = subprocess.run(
        ["pulumi", "stack", "output", "--json"],
        capture_output=True, text=True, check=True, cwd=PULUMI_DIR,
    )
    return json.loads(result.stdout)


def wait_for_ssm_ready(instance_id: str, timeout: int = 120) -> None:
    ssm = boto3.client("ssm", region_name=REGION)
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = ssm.describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
        )
        if resp["InstanceInformationList"]:
            print(f"  SSM agent ready on {instance_id}")
            return
        print("  Waiting for SSM agent...")
        time.sleep(10)
    print(f"SSM agent not ready on {instance_id} within {timeout}s", file=sys.stderr)
    sys.exit(1)


def spike_cpu(instance_id: str) -> str:
    ssm = boto3.client("ssm", region_name=REGION)
    # Install stress-ng in case user_data hasn't finished, then spike all CPUs for 180s
    resp = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [
            "dnf install -y stress-ng 2>/dev/null || true",
            "stress-ng --cpu 0 --timeout 180s &",
        ]},
    )
    command_id = resp["Command"]["CommandId"]
    print(f"  SSM command sent: {command_id}")
    return command_id


def wait_for_alarm(alarm_name: str, timeout: int = 360) -> None:
    cw = boto3.client("cloudwatch", region_name=REGION)
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
    print(f"✗ Alarm did not reach ALARM state within {timeout}s", file=sys.stderr)
    sys.exit(1)


def test_trigger_alarm():
    outputs = get_stack_outputs()
    instance_id = outputs["instance_id"]
    alarm_name = outputs["alarm_name"]

    print(f"\nInstance: {instance_id}")
    print(f"Alarm:    {alarm_name}")

    wait_for_ssm_ready(instance_id)
    spike_cpu(instance_id)
    wait_for_alarm(alarm_name)


if __name__ == "__main__":
    test_trigger_alarm()
