"""
Slack Interactivity Lambda — handles button clicks from the #incidents Block Kit message.

Invocation path:
  User clicks "Create War Room Channel" in the #incidents Slack message
    → Slack POSTs to this Lambda's API Gateway URL (the Interactivity Request URL
      configured in the Slack App settings after pulumi up)
    → creates a dedicated #inc-<number> channel and invites on-call users
    → updates the original message to replace the button with a confirmation

Security:
  Every request is verified using the Slack signing secret (HMAC-SHA256 over
  the raw request body + timestamp). Requests that fail verification or arrive
  more than 5 minutes after their timestamp are rejected with HTTP 403.
  Never skip this check — the endpoint is publicly accessible.

Idempotency:
  If the channel already exists (name_taken), the handler looks it up and
  continues rather than failing. This handles the case where the button is
  clicked more than once before the message is updated.

Post-deploy wiring:
  The Slack App's Interactivity Request URL must be set to the value of the
  slack_interactivity_url Pulumi output after each pulumi up. See README.md
  Post-deploy wiring and SLACK_APP_SETUP.md Step 5.
"""
import hashlib
import hmac
import json
import os
import time
import urllib.parse

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"]
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
ONCALL_SLACK_USER_IDS = [u for u in os.environ.get("ONCALL_SLACK_USER_IDS", "").split(",") if u]


def _verify_slack_signature(event: dict) -> bool:
    timestamp = event.get("headers", {}).get("x-slack-request-timestamp", "")
    if not timestamp or abs(time.time() - int(timestamp)) > 300:
        return False
    sig_basestring = f"v0:{timestamp}:{event['body']}"
    expected = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()
    received = event.get("headers", {}).get("x-slack-signature", "")
    return hmac.compare_digest(expected, received)


def _get_or_create_channel(client: WebClient, name: str) -> str:
    try:
        resp = client.conversations_create(name=name)
        return resp["channel"]["id"]
    except SlackApiError as e:
        if e.response["error"] != "name_taken":
            raise
    # Channel already exists — look it up
    cursor = None
    while True:
        resp = client.conversations_list(limit=200, cursor=cursor, types="public_channel,private_channel")
        for ch in resp["channels"]:
            if ch["name"] == name:
                return ch["id"]
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            raise RuntimeError(f"Channel '{name}' not found after name_taken error")


def handler(event, context):
    if not _verify_slack_signature(event):
        return {"statusCode": 403, "body": "Forbidden"}

    body = urllib.parse.unquote_plus(event.get("body", ""))
    payload = json.loads(body.removeprefix("payload="))

    action = payload["actions"][0]
    action_id = action["action_id"]
    incident_id = action.get("value", "unknown")
    origin_channel = payload["channel"]["id"]
    message_ts = payload["message"]["ts"]

    client = WebClient(token=SLACK_BOT_TOKEN)

    if action_id == "create_war_room":
        channel_name = f"inc-{incident_id.lower().replace('_', '-')}"
        war_room_id = _get_or_create_channel(client, channel_name)

        if ONCALL_SLACK_USER_IDS:
            client.conversations_invite(channel=war_room_id, users=ONCALL_SLACK_USER_IDS)

        client.chat_postMessage(
            channel=war_room_id,
            text=f":rotating_light: War room for incident `{incident_id}`. All responders please join.",
        )

        # Replace the buttons in the original message with a confirmation
        client.chat_update(
            channel=origin_channel,
            ts=message_ts,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":white_check_mark: War room created: <#{war_room_id}|{channel_name}>",
                    },
                }
            ],
            text=f"War room created: #{channel_name}",
        )

    return {"statusCode": 200, "body": ""}
