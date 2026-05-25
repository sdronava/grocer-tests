import json
import subprocess
from pathlib import Path

import pytest

PULUMI_DIR = Path(__file__).parent.parent


@pytest.fixture(scope="session")
def outputs():
    result = subprocess.run(
        ["pulumi", "stack", "output", "--json"],
        capture_output=True, text=True, check=True, cwd=PULUMI_DIR,
    )
    return json.loads(result.stdout)


@pytest.fixture(scope="session")
def endpoint_url(outputs):
    return outputs["endpoint_url"]
