"""
Test 1 — API Gateway → Lambda invocation.

Sends a GET /sleep request and asserts:
  - HTTP 200
  - Response body contains slept_seconds=7
  - Elapsed time >= 7s (proves Lambda actually executed the sleep)
"""

import time

import requests


def test_lambda_sleep(endpoint_url):
    start = time.time()
    resp = requests.get(endpoint_url, timeout=30)
    elapsed = time.time() - start

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    body = resp.json()
    assert body.get("slept_seconds") == 7, f"Unexpected body: {body}"
    assert elapsed >= 7.0, f"Expected >= 7s elapsed but got {elapsed:.2f}s"

    print(f"\n✓ Response in {elapsed:.2f}s — {body}")
