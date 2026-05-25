# Slack App Setup — War Room Channel Creator

This Slack App receives button clicks from the `#incidents` channel and creates a
dedicated war-room channel for the incident. It is deployed as an AWS Lambda and tested
manually — it is not part of the automated test suite.

---

## Step 1: Create the Slack App

1. Go to https://api.slack.com/apps and click **Create New App → From scratch**.
2. Name: `grocer-incident-responder`
3. Workspace: select your workspace.

---

## Step 2: Configure OAuth Scopes

In the app settings go to **OAuth & Permissions → Scopes → Bot Token Scopes** and add:

| Scope | Purpose |
|---|---|
| `channels:manage` | Create public channels |
| `groups:write` | Create private channels |
| `channels:read` | Look up existing channels |
| `groups:read` | Look up existing private channels |
| `chat:write` | Post messages |
| `users:read` | Resolve user IDs (optional, for display names) |

Click **Install to Workspace** and copy the **Bot User OAuth Token** (`xoxb-...`).
This is your `slack_bot_token` Pulumi secret.

---

## Step 3: Note the Signing Secret

In **Basic Information → App Credentials**, copy the **Signing Secret**.
This is your `slack_signing_secret` Pulumi secret.

---

## Step 4: Deploy the Lambda

Run `pulumi up` for test05. After the stack is up, note the output value
`slack_interactivity_url` — it will look like:
```
https://<id>.execute-api.<region>.amazonaws.com/slack/interactivity
```

---

## Step 5: Enable Interactivity

In the Slack App settings go to **Interactivity & Shortcuts → Interactivity → On**.

Set **Request URL** to the `slack_interactivity_url` output from Step 4.

Click **Save Changes**. Slack will verify the URL is reachable and returns HTTP 200.

---

## Step 6: Verify the Block Kit Message Format

The PagerDuty native Slack extension posts the initial message to `#incidents`. For the
"Create War Room" button to work, the message must include an `actions` block with
`action_id: "create_war_room"` and `value` set to the PagerDuty incident ID.

The Incident Workflow Slack action in PagerDuty should be configured with a custom
message body like:

```json
{
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*:rotating_light: P1 Incident triggered*\n*Service:* {{service.name}}\n*Incident:* <{{incident.html_url}}|{{incident.title}}>\n*Acknowledged by:* {{responder.name}}"
      }
    },
    {
      "type": "actions",
      "elements": [
        {
          "type": "button",
          "text": { "type": "plain_text", "text": "Create War Room" },
          "style": "danger",
          "action_id": "create_war_room",
          "value": "{{incident.id}}"
        }
      ]
    }
  ]
}
```

Note: PagerDuty's Slack action supports a subset of Block Kit. If template variables
like `{{incident.id}}` are not supported in the native action, post the initial Slack
message from the Meet Lambda instead (which already has full incident context from the
PD Automation Action payload).

---

## Step 7: Manual Test

1. Trigger a PagerDuty incident (run test steps 1–2 from the test suite, or use
   `pulumi stack output` to get the alarm name and set it manually via AWS CLI).
2. Acknowledge the incident in PagerDuty.
3. Watch `#incidents` for the Block Kit message.
4. Click **Create War Room**.
5. Verify:
   - A new channel named `#inc-<incident-id>` is created.
   - The on-call users listed in `oncall_slack_user_ids` are members.
   - A pinned intro message appears in the war-room channel.
   - The original `#incidents` message button is replaced with
     `:white_check_mark: War room created: #inc-<incident-id>`.

---

## Lambda Code

See `slack_app/handler.py` in this folder.

**Environment variables the Lambda needs:**

| Variable | Value |
|---|---|
| `SLACK_BOT_TOKEN` | `xoxb-...` bot token |
| `SLACK_SIGNING_SECRET` | Signing secret from Step 3 |
| `ONCALL_SLACK_USER_IDS` | Comma-separated Slack user IDs, e.g. `U111AAA,U222BBB` |

These are set from Pulumi config secrets — do not hardcode them.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Slack shows "This app failed to respond" | Lambda timed out or returned non-200 | Check Lambda logs in CloudWatch; Slack expects 200 within 3 seconds |
| `invalid_auth` from Slack SDK | Wrong bot token | Re-check `slack_bot_token` config secret |
| `channel_not_found` when inviting users | Bot is not a member of the origin channel | Invite the bot to `#incidents` manually |
| Signature verification fails | Request URL mismatch or clock skew | Ensure Lambda system clock is accurate (it is by default on AWS) |
| `name_taken` not handled | Channel already exists | Handler already handles this — check logs for other errors |
