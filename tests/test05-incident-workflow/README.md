# Test 05 — Incident Workflow on Acknowledgement

Proves that when a heartbeat alarm fires and an on-call engineer acknowledges the
PagerDuty incident, an automated workflow creates a Jira ticket, schedules a Google
Meet starting in 30 minutes, and posts a rich Slack message with a button to spin up
a dedicated war-room channel.

---

## What happens end-to-end

```
1. A Lambda endpoint receives periodic heartbeat calls.
2. CloudWatch detects missing heartbeats → fires an alarm.
3. SNS delivers the alarm to PagerDuty → incident is triggered.
4. On-call engineer acknowledges the incident (via PagerDuty app or test script).
5. PagerDuty V3 webhook fires the Workflow Lambda, which:
      a. Creates a Jira ticket in the configured project.
      b. Creates a Google Calendar event (with Meet link) starting in 30 minutes.
      c. Posts a Block Kit message to #incidents in Slack with:
            – links to the Jira ticket, PagerDuty incident, and Google Meet
            – a "Create War Room Channel" button (handled by the Slack App Lambda)
6. Clicking the button creates a dedicated #inc-NNN Slack channel and invites on-call users.
7. The test script resolves the incident to clean up.
```

---

## Prerequisites

### Tools

| Tool | Version | Install |
|---|---|---|
| Python | 3.12+ | https://python.org |
| uv | latest | `pip install uv` |
| Pulumi CLI | 3.x | https://www.pulumi.com/docs/install/ |
| AWS CLI v2 | latest | https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html |
| git | any | — |

### Accounts you need

- **AWS** — IAM user or SSO role with permissions to create Lambda, API Gateway,
  CloudWatch, SNS, and IAM resources.
- **PagerDuty** — A working account. You need a user ID to target for escalations.
- **Jira Cloud** — An Atlassian account with a project to create issues in.
- **Slack** — A workspace where you can create apps and post messages.
- **GCP** — A Google Cloud project with the Calendar API enabled (free tier is fine).

---

## One-time account setup

These steps are done once per environment. They cannot be automated by Pulumi.

### 1. AWS SSO / credentials

Log in to AWS and confirm your profile works:

```bash
aws sso login --sso-session <your-sso-session>
aws sts get-caller-identity --profile <your-aws-profile>
```

Set the profile for your terminal session:

```bash
export AWS_PROFILE=<your-aws-profile>
```

### 2. Jira API token

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token** → give it a name → copy the token.

You will need:
- Your Jira site URL: `https://<org>.atlassian.net`
- The project key (visible on any issue URL, e.g. `IR`)
- The issue type name (open an existing issue → note the **Issue Type** field, e.g. `Incident`)
- Your Atlassian account email
- The API token from above

### 3. Slack App

Create the Slack App that powers the "Create War Room" button.

1. Go to https://api.slack.com/apps → **Create New App → From scratch**
   - Name: `grocer-incident-responder`
   - Workspace: your workspace
2. **OAuth & Permissions → Bot Token Scopes** — add:
   `channels:manage`, `groups:write`, `channels:read`, `groups:read`, `chat:write`
3. **Install to Workspace** → copy the `xoxb-...` **Bot User OAuth Token**
4. **Basic Information → App Credentials** → copy the **Signing Secret**

> The **Interactivity Request URL** is filled in after `pulumi up` — see Post-deploy
> wiring below.

### 4. GCP service account

1. Go to https://console.cloud.google.com
2. **APIs & Services → Enable APIs** → search **Google Calendar API** → Enable
3. **IAM & Admin → Service Accounts → Create Service Account**
   - Name: `grocer-incident-responder`
   - Skip role assignment (permissions come from calendar sharing)
4. Click the service account → **Keys → Add Key → Create new key → JSON** → download
5. Share your calendar with the service account:
   - Google Calendar → gear → Settings → click your calendar name → **Share with specific people**
   - Add the service account email (shown on the service account detail page)
   - Permission: **Make changes to events** → Save

---

## Setup

### 1. Clone and install base dependencies

```bash
git clone <repo-url>
cd grocer-tests
uv pip sync pyproject.toml
```

> **Python environment note — read before proceeding:**
>
> There are two separate Python environments in this test. You do not set either of them
> up manually.
>
> | Environment | What it is | How it is created |
> |---|---|---|
> | **Pulumi stack venv** (`.venv/` in this folder) | Runs the Pulumi program (`__main__.py`) and test scripts | Created automatically by Pulumi on the first `pulumi preview` or `pulumi up` |
> | **Lambda bundle dirs** (`lambdas/workflow/`, `slack_app/`) | Dependencies zipped into the Lambda deployment packages | Created by running `./build.sh` (Step 4 below) |
>
> `build.sh` uses `uv pip install --target`, which installs directly into a directory
> without needing an active venv. Run it any time before `pulumi up`.

### 2. Install and configure the Pulumi stack

```bash
cd tests/test05-incident-workflow
pulumi stack init grocer-tests-test05-dev
```

Set all config values (replace placeholders with your real values):

```bash
# Non-secret config
pulumi config set alarm_source_ip            $(curl -s https://api.ipify.org)
pulumi config set jira_site_url              https://<org>.atlassian.net
pulumi config set jira_project_key           IR
pulumi config set jira_issue_type            Incident
pulumi config set slack_incidents_channel_id C0123ABC456
pulumi config set oncall_slack_user_ids      U111AAA,U222BBB
pulumi config set google_calendar_id         your.email@gmail.com
pulumi config set pd_escalation_target_user_id PXXXXXX

# Secrets
pulumi config set --secret jira_user_email           you@example.com
pulumi config set --secret jira_api_token            <jira-api-token>
pulumi config set --secret slack_bot_token           xoxb-...
pulumi config set --secret slack_signing_secret      <signing-secret>
pulumi config set --secret google_service_account_key "$(cat /path/to/sa-key.json)"
```

**How to find each value:**

| Key | Where to find it |
|---|---|
| `alarm_source_ip` | Auto-detected via `curl` above |
| `jira_site_url` | Browser URL when logged into Jira |
| `jira_project_key` | Shown next to the project name in Jira, or in issue URLs |
| `jira_issue_type` | Open any existing issue → note the **Issue Type** field value |
| `slack_incidents_channel_id` | Slack: right-click channel → Copy Link → last URL segment (starts with `C`) |
| `oncall_slack_user_ids` | Slack: click a user's profile → `...` → **Copy member ID** (starts with `U`) |
| `google_calendar_id` | Google Calendar → Settings → your calendar → **Integrate calendar** → Calendar ID |
| `pd_escalation_target_user_id` | PagerDuty → Users → click your user → ID in the URL |
| `jira_user_email` | Your Atlassian login email |
| `jira_api_token` | Created in One-time setup Step 2 above |
| `slack_bot_token` | `xoxb-...` token from One-time setup Step 3 |
| `slack_signing_secret` | Signing secret from One-time setup Step 3 |
| `google_service_account_key` | Path to downloaded JSON key from One-time setup Step 4 |

### 3. Create the Pulumi stack venv

Pulumi needs its own virtual environment to run `__main__.py`. Create it once:

```bash
uv venv .venv
uv pip install -r requirements.txt
```

This installs `pulumi`, `pulumi-aws`, `pulumi-pagerduty`, and the shared library into
`.venv/`. It is separate from the Lambda bundle directories and only needs to be done
once (or after adding a new dependency to `requirements.txt`).

### 4. Install Lambda dependencies

No venv activation needed. Run:

```bash
./build.sh
```

This uses `uv pip install --target` to install Python packages directly into
`lambdas/workflow/` and `slack_app/` so they are bundled into the Lambda deployment
zips. Re-run this any time you change a `requirements.txt` or `handler.py`.

### 5. Preview the infrastructure

```bash
pulumi preview
```

Expect approximately 20 resources: 2 Lambdas, 2 API Gateways, CloudWatch alarm + metric
filter, SNS topic + subscription, 2 IAM roles, PagerDuty service + escalation policy +
webhook subscription.

Review the diff. Do not proceed if anything looks unexpected.

---

## Deploy

```bash
pulumi up --yes
```

### Post-deploy wiring (required before testing)

After `pulumi up` completes, copy the Slack App interactivity URL into your Slack App:

```bash
pulumi stack output slack_interactivity_url
```

Then:
1. Go to https://api.slack.com/apps → select `grocer-incident-responder`
2. **Interactivity & Shortcuts → Interactivity → On**
3. Paste the URL into **Request URL**
4. Click **Save Changes**

---

## Run the automated tests

Export secrets as environment variables before running pytest (Pulumi secrets are not
exposed as outputs — pytest reads them directly from env vars):

```bash
export PAGERDUTY_TOKEN=<your-pd-api-token>
export SLACK_BOT_TOKEN=<your-slack-bot-token>
export JIRA_USER_EMAIL=<your-jira-email>
export JIRA_API_TOKEN=<your-jira-api-token>
```

Run the full suite:

```bash
uv run pytest tests/ -v -s
```

**Expected duration: 20–30 minutes** (dominated by CloudWatch evaluation windows).

The tests run in order:

| Test | What it does | Expected duration |
|---|---|---|
| `test_01_send_heartbeat` | Sends one request, waits for alarm → OK | ~4 min |
| `test_02_trigger_alarm` | Stops sending, waits for alarm → ALARM and PD incident → triggered | ~4 min |
| `test_03_acknowledge` | Acknowledges the PD incident, waits 30s for Lambda to run | ~1 min |
| `test_04_verify_workflow` | Checks Jira ticket, Slack Block Kit message, and Meet link | ~1 min |
| `test_05_resolve` | Resolves the PD incident, confirms final state | <1 min |

---

## Manual Slack App test

After the automated tests complete (incident resolved), you can test the war-room button
manually:

1. Find the Block Kit message in your `#incidents` Slack channel.
2. Click **Create War Room Channel**.
3. Verify:
   - A new channel named `#inc-<number>` is created.
   - The on-call users listed in `oncall_slack_user_ids` are members.
   - A pinned intro message appears in the new channel.
   - The original `#incidents` message buttons are replaced with a confirmation.

For full details see `SLACK_APP_SETUP.md`.

---

## Tear down

```bash
pulumi destroy --yes
```

Removes all AWS and PagerDuty resources created by this stack.

**Manual cleanup required after destroy:**

- Jira tickets created during the test (archive or delete in Jira)
- The `#inc-*` war-room channel in Slack (archive in Slack)
- The Block Kit message in `#incidents` (delete in Slack)
- The Google Calendar event (delete in Google Calendar)

Confirm no resources tagged `test=test05` remain in the AWS console.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `NoCredentialProviders` on `pulumi up` | AWS profile not set | `export AWS_PROFILE=<profile>` |
| `pulumi preview` shows 0 resources | Wrong stack selected | `pulumi stack select grocer-tests-test05-dev` |
| Alarm stays `INSUFFICIENT_DATA` | `alarm_source_ip` does not match your current IP | `pulumi config set alarm_source_ip $(curl -s https://api.ipify.org)` then re-deploy |
| Jira ticket not created | Wrong `jira_issue_type` value | Check issue type in Jira project settings; update config and redeploy |
| Slack message not posted | Bot not invited to channel | Invite the bot: `/invite @grocer-incident-responder` in `#incidents` |
| Meet link missing from Slack message | Service account not shared on calendar | Re-check calendar sharing with the service account email |
| War-room button returns "This app failed" | Interactivity URL not set or Lambda timeout | Check Lambda logs in CloudWatch; re-paste URL in Slack App settings |
| `PAGERDUTY_TOKEN env var not set` | Missing env var before pytest | `export PAGERDUTY_TOKEN=<token>` |
