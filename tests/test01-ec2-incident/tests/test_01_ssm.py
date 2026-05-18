"""
Test 1 — SSM connectivity.

Verifies the SSM agent can receive and execute a command on the instance.
This is a precondition for test_02 (which uses SSM to spike CPU).
"""

import time

import pytest


def test_ssm_command(instance_id, ssm):
    resp = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": ["echo SSM OK"]},
    )
    command_id = resp["Command"]["CommandId"]
    print(f"\n  Command sent: {command_id}")

    deadline = time.time() + 60
    while time.time() < deadline:
        time.sleep(5)
        result = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        status = result["Status"]
        if status == "Success":
            output = result["StandardOutputContent"].strip()
            print(f"✓ Output: '{output}'")
            assert output == "SSM OK"
            return
        if status in ("Failed", "TimedOut", "Cancelled"):
            pytest.fail(f"Command {status}: {result.get('StandardErrorContent', '')}")
        print(f"  Status: {status}")

    pytest.fail("SSM command did not complete within 60s")
