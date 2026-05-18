"""
Verify SSM Session Manager connectivity to the test EC2 instance.

Side-effects:
  - Polls SSM until the agent registers (read-only)
  - Sends a single SSM RunShellScript command ("echo SSM OK")

Run:
  uv run python scripts/verify_ssm.py
  uv run pytest scripts/verify_ssm.py -v -s
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


def wait_for_ssm_ready(instance_id: str, timeout: int = 300) -> None:
    ssm = boto3.client("ssm", region_name=REGION)
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = ssm.describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
        )
        if resp["InstanceInformationList"]:
            info = resp["InstanceInformationList"][0]
            print(f"✓ SSM agent online — version {info['AgentVersion']} on {instance_id}")
            return
        elapsed = int(timeout - (deadline - time.time()))
        print(f"  Waiting for SSM agent... ({elapsed}s / {timeout}s)")
        time.sleep(15)
    print(f"✗ SSM agent did not come online within {timeout}s", file=sys.stderr)
    sys.exit(1)


def run_test_command(instance_id: str) -> None:
    ssm = boto3.client("ssm", region_name=REGION)
    resp = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": ["echo SSM OK"]},
    )
    command_id = resp["Command"]["CommandId"]
    print(f"  SSM command sent: {command_id}")

    deadline = time.time() + 60
    while time.time() < deadline:
        time.sleep(5)
        result = ssm.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id,
        )
        status = result["Status"]
        if status == "Success":
            output = result["StandardOutputContent"].strip()
            print(f"✓ Command output: '{output}'")
            assert output == "SSM OK", f"Unexpected output: {output!r}"
            return
        if status in ("Failed", "TimedOut", "Cancelled"):
            print(f"✗ Command failed: {status}", file=sys.stderr)
            print(result.get("StandardErrorContent", ""), file=sys.stderr)
            sys.exit(1)
        print(f"  Command status: {status}")

    print("✗ Command did not complete within 60s", file=sys.stderr)
    sys.exit(1)


def test_ssm_connectivity():
    outputs = get_stack_outputs()
    instance_id = outputs["instance_id"]
    print(f"\nInstance: {instance_id}")
    wait_for_ssm_ready(instance_id)
    run_test_command(instance_id)


if __name__ == "__main__":
    test_ssm_connectivity()
