# Test 05 — Incident Workflow on Acknowledgement

## Scope

**Proves:** When a heartbeat alarm fires (same mechanism as test04) and the on-call
acknowledges the PagerDuty incident, a PagerDuty Incident Workflow automatically:
- Creates a Jira ticket (PagerDuty native Jira extension)
- Posts a Block Kit message with an action button to a Slack channel (PagerDuty native Slack extension)
- Schedules a Google Meet 30 minutes out (PagerDuty Automation Action → Lambda)

The Block Kit message includes a "Create War Room" button. Clicking it (tested manually)
creates a dedicated Slack incident channel and invites on-call users via a custom Slack App.

**Does not cover:** Auto-resolution, multi-responder escalation, postmortem tracking.

**Key difference from test04:** No `ok_actions` on the CloudWatch alarm — the incident
stays open until explicitly resolved by the test script.

---

## Architecture

```
CloudWatch Alarm (missing heartbeat)
        │
        ▼
      SNS Topic ──────────────────────► PagerDuty incident triggered
                                                │
                                     on-call acknowledges
                                                │
                                    Incident Workflow fires
                                                │
                          ┌─────────────────────┼──────────────────────┐
                          ▼                     ▼                      ▼
              PD native Jira ext     PD native Slack ext     PD Automation Action
              Creates Jira ticket    Posts Block Kit msg            │
                                     to #incidents                  ▼
                                     (with button)         Lambda (webhook handler)
                                                           Calls Google Calendar API
                                                           Creates Meet (starts in 30m)
                                                           Posts Meet link to Slack

                                     [manual] user clicks "Create War Room"
                                                │
                                                ▼
                                     Slack Interactivity Lambda
                                     Creates #inc-NNN channel
                                     Invites on-call users
                                     Updates original message
```

---

## Infrastructure Plan

Stack: `grocer-tests-test05-dev`

### AWS Resources (Pulumi-managed)

| Resource | Details |
|---|---|
| API Gateway + Lambda (heartbeat) | Python 3.12, `GET /invoke`, sleep capped at 5s, 10s timeout |
| CloudWatch Log Group | `/aws/apigateway/grocer-test05`, 1-day retention |
| CloudWatch Metric Filter | `{ $.sourceIp = "*" }`, emits `RequestCount=1` (Count) with `SourceIp` dimension |
| CloudWatch Metric Alarm | `Sum < 1` over 2-min window, `treat_missing_data=breaching`, **no `ok_actions`** |
| SNS Topic + HTTPS subscription | → PagerDuty CloudWatch SNS adapter |
| Lambda + API Gateway (Meet webhook) | Receives PD Automation Action POST; creates Google Meet via Calendar API; posts Meet link to Slack |
| Lambda + API Gateway (Slack interactivity) | Receives Slack button-click POST; creates war-room channel; invites users |
| IAM roles | Least-privilege execution roles for both Lambdas |

### PagerDuty Resources (Pulumi-managed)

| Resource | Details |
|---|---|
| PagerDuty Service | Wired to SNS via CloudWatch adapter |
| PagerDuty Escalation Policy | Single target: configured on-call user |
| PagerDuty Incident Workflow | Trigger: `incident.acknowledged`; steps: Jira ticket, Slack message, Automation Action |
| PagerDuty Automation Action | Webhook pointing to the Meet Lambda URL |

### Not Pulumi-managed (one-time account setup)

| What | Where |
|---|---|
| PagerDuty ↔ Jira Cloud extension | PD UI → Apps & Add-ons → Jira Cloud |
| PagerDuty ↔ Slack extension | PD UI → Integrations → Slack |
| Slack App (for war-room button) | api.slack.com — see `SLACK_APP_SETUP.md` |

---

## Incident Workflow Steps

1. **Create Jira ticket** — PagerDuty native Jira Cloud action. Creates an issue in the
   configured project with incident title, severity, and a link back to PagerDuty.
   Bi-directional sync: resolving the PD incident closes the Jira ticket.

2. **Post Slack notification** — PagerDuty native Slack action. Posts a Block Kit message
   to `#incidents` with: incident title, service, acknowledging user, and a
   "Create War Room" button. The button `value` carries the PD incident ID.

3. **Fire Automation Action** — PagerDuty calls the Meet Lambda via HTTPS POST with
   incident context. Lambda creates a Google Calendar event (Meet enabled) starting
   30 minutes from invocation and posts the Meet link to Slack as a follow-up message.

---

## Test Logic Plan

1. **test_01_send_heartbeat** — `GET /invoke`. Poll up to 7 min for alarm → `OK`.

2. **test_02_trigger_alarm** — Stop sending. Poll up to 7 min for alarm → `ALARM`
   and PD incident → `triggered`.

3. **test_03_acknowledge** — Acknowledge incident via PagerDuty Events API.
   Poll for Incident Workflow completion (up to 2 min).

4. **test_04_verify_jira** — Poll Jira REST API. Assert ticket exists with incident title
   and a PagerDuty link in the description.

5. **test_05_verify_slack** — Poll Slack API (`conversations.history` on `#incidents`).
   Assert Block Kit message with "Create War Room" button is present.

6. **test_06_verify_meet** — Poll Slack API. Assert a follow-up message containing a
   `meet.google.com` link was posted by the Lambda.

7. **test_07_resolve** — Resolve incident via PagerDuty Events API. Assert state →
   `resolved`. Assert Jira ticket transitions to Done/Closed.

**Estimated automated test time:** 20–30 minutes.

**Manual test (separate):** Click "Create War Room" button in Slack. Verify dedicated
channel created and on-call users invited. See `SLACK_APP_SETUP.md`.

---

## Teardown Plan

```bash
pulumi destroy --yes
```

Removes: all Lambda functions, API Gateways, CloudWatch resources, SNS, IAM roles,
PagerDuty Service, Escalation Policy, Incident Workflow, Automation Action.

**Manual cleanup required:**
- Jira tickets created during tests (archive or delete manually)
- Slack messages and any war-room channels (archive manually)
- Google Calendar events (delete manually)

Verify: no AWS resources tagged `test=test05` remain; no orphaned PagerDuty resources.

---

## Required Config

### Already available

| Key | Source |
|---|---|
| `pagerduty:token` | Pulumi secret from previous tests |
| `pd_escalation_target_user_id` | Set in test04 |

### New — set before `pulumi up`

```bash
# Heartbeat alarm
pulumi config set alarm_source_ip $(curl -s https://api.ipify.org)

# Jira
pulumi config set jira_site_url       https://yourorg.atlassian.net
pulumi config set jira_project_key    INC
pulumi config set jira_issue_type     Incident

# Slack
pulumi config set slack_incidents_channel_id   C0123ABC456
pulumi config set oncall_slack_user_ids        U111AAA,U222BBB

# Google Calendar
pulumi config set google_calendar_id  your.email@example.com

# Secrets
pulumi config set --secret slack_bot_token            xoxb-...
pulumi config set --secret slack_signing_secret       abc123...
pulumi config set --secret google_service_account_key "$(cat sa-key.json)"
```

### GCP service account requirements

- Google Calendar API enabled in the GCP project
- Service account added as an editor on `google_calendar_id` calendar
  (Google Calendar Settings → Share with specific people → add service account email)

---

## Library Changes Anticipated

- **`grocer_pulumi_resources/`**: No changes expected.
- **`grocer_pulumi_components/`**: May extract a `WebhookLambda` component
  (API Gateway + Lambda with a public URL) if the pattern is used for both
  the Meet Lambda and the Slack interactivity Lambda.
