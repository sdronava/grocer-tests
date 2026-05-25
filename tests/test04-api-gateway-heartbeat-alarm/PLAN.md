# Test 04 — API Gateway Heartbeat Alarm (Missing Invocations)

## Scope

**Proves:** A CloudWatch alarm fires when a specific source IP stops invoking the Lambda
for 5 minutes, and clears when invocations resume.

**Does not cover:** Multi-IP monitoring, SNS/PagerDuty notifications, or sustained load.

---

## Infrastructure Plan

Stack: `grocer-tests-test04-dev`

| Resource | Details |
|---|---|
| API Gateway HTTP API | Protocol: HTTP, `$default` stage with auto-deploy |
| Lambda function | Python 3.12, reads `?sleep=N` (capped at 5s), 10s timeout |
| CloudWatch Log Group | `/aws/apigateway/grocer-test04`, 1-day retention |
| CloudWatch Metric Filter | Pattern: `{ $.sourceIp = "*" }`, emits `RequestCount=1` (Count) with `SourceIp` dimension extracted per log entry |
| CloudWatch Metric Alarm | Namespace: `grocer/ApiGateway/test04`, metric: `RequestCount`, dimension: `SourceIp=<alarm_source_ip>`, threshold: `Sum < 1`, period: 300s, treat_missing_data: **breaching** → fires when no invocations in any 5-minute window |

**Pre-provision config required:**
```bash
pulumi config set alarm_source_ip $(curl -s https://api.ipify.org)
```

---

## How the alarm works

`treat_missing_data=breaching` means an evaluation window with zero data points is treated
as though the metric was below the threshold (Sum < 1 = breach). This turns a missing-data
alarm into a heartbeat: the alarm stays OK only while requests keep arriving.

---

## Test Logic Plan

1. **test_01_send_request** — Send `GET /invoke?sleep=3`. Assert HTTP 200.
   Poll up to 7 min for alarm to reach `OK` (one 300s evaluation period + processing lag).

2. **test_02_wait_for_alarm** — Send no requests. Poll up to 7 min for alarm to reach `ALARM`
   (the 5-minute window empties and missing data = breaching).

3. **test_03_send_request_recovers** — Send `GET /invoke?sleep=3`. Assert HTTP 200.
   Poll up to 7 min for alarm to return to `OK`.

**Total estimated test time:** 15–21 minutes.

---

## Teardown Plan

```bash
pulumi destroy --yes
```

Removes: Lambda, API Gateway, Log Group, Metric Filter, Metric Alarm, IAM role.

Verify in AWS console: no resources tagged `test=test04` remain.

---

## Library Changes

- **`grocer_pulumi_resources/alerting.py`**: `GrocerMetricAlarm` now accepts a
  `treat_missing_data` parameter (default: `"notBreaching"` — backward compatible).
  Test04 passes `"breaching"` to flip the alarm semantics.
