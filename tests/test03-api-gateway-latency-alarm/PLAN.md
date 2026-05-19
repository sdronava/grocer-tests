# Test 03 — API Gateway Latency Alarm by Source IP

## Scope

**Proves:** A CloudWatch alarm fires when requests from a specific source IP take longer
than 10 seconds, and recovers automatically when latency returns to normal.

**Does not cover:** Multi-IP filtering, alarm notifications (SNS/PagerDuty), or sustained
load testing.

---

## Infrastructure Plan

Stack: `grocer-tests-test03-dev`

| Resource | Details |
|---|---|
| API Gateway HTTP API | Protocol: HTTP, `$default` stage with auto-deploy |
| Lambda function | Python 3.12, reads `?sleep=N` from query string, 30s timeout |
| CloudWatch Log Group | `/aws/apigateway/grocer-test03`, 1-day retention |
| CloudWatch Metric Filter | Pattern: `{ $.sourceIp = "*" }`, emits `IntegrationLatency` metric (ms) with `SourceIp` dimension extracted from each log entry |
| CloudWatch Metric Alarm | Namespace: `grocer/ApiGateway/test03`, metric: `IntegrationLatency`, dimension: `SourceIp=<alarm_source_ip>`, threshold: `> 10000 ms`, period: 60s, statistic: Maximum, treat_missing_data: notBreaching |

**Pre-provision config required:**
```bash
pulumi config set alarm_source_ip $(curl -s https://api.ipify.org)
```

---

## Test Logic Plan

1. **test_01_fast_request** — Send `GET /sleep?sleep=5`. Assert HTTP 200 and `slept_seconds=5`.
   Wait 90s for CloudWatch to evaluate. Assert alarm is `OK` or `INSUFFICIENT_DATA`.

2. **test_02_slow_request** — Send `GET /sleep?sleep=12`. Assert HTTP 200 and `slept_seconds=12`.
   Poll alarm state up to 180s. Assert alarm transitions to `ALARM`.

3. **test_03_alarm_recovers** — Send no further requests. Poll alarm state up to 180s.
   Assert alarm returns to `OK` (treat_missing_data=notBreaching clears it after one empty period).

---

## Teardown Plan

```bash
pulumi destroy --yes
```

Removes: Lambda, API Gateway, Log Group, Metric Filter, Metric Alarm, IAM role.

Verify in AWS console: no resources tagged `test=test03` remain.

---

## Library Changes

- **`grocer_pulumi_resources/alerting.py`**: Added `GrocerMetricFilter` wrapper
- **`grocer_pulumi_resources/__init__.py`**: Exported `GrocerMetricFilter`
- **`grocer_pulumi_resources/serverless.py`**: Updated default access log format to emit `integrationLatency` and `responseLatency` as JSON numbers (unquoted) for reliable metric filter extraction
