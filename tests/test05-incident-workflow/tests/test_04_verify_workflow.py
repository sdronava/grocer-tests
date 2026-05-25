"""
Test 4 — Verify the three workflow side-effects fired after acknowledgement:
  4a. Jira ticket created for this incident.
  4b. Slack Block Kit message posted to #incidents with the war-room button.
  4c. Slack message contains a meet.google.com link (posted by the Lambda).
"""
import base64
import time

import requests
from slack_sdk import WebClient

PD_API        = "https://api.pagerduty.com"
MAX_WAIT      = 60
POLL_INTERVAL = 10


# ── 4a: Jira ────────────────────────────────────────────────────────────────

def test_jira_ticket_created(pd_service_id, pd_headers, jira_site_url, jira_project_key, jira_auth):
    # Derive the incident title from the acknowledged PD incident.
    resp = requests.get(
        f"{PD_API}/incidents",
        headers=pd_headers,
        params={"service_ids[]": pd_service_id, "statuses[]": "acknowledged"},
    )
    assert resp.status_code == 200
    incidents = resp.json().get("incidents", [])
    assert incidents, "No acknowledged incident found — run test_03 first"
    incident_number = incidents[0]["incident_number"]

    email, token = jira_auth
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Accept": "application/json",
    }

    print(f"\nSearching Jira project {jira_project_key} for INC-{incident_number}...")
    deadline = time.time() + MAX_WAIT
    found_key = None
    while time.time() < deadline:
        # JQL text search splits on hyphens so 'summary ~ "INC-14"' is unreliable.
        # Fetch recent issues and match in Python instead.
        resp = requests.get(
            f"{jira_site_url}/rest/api/3/search/jql",
            headers=headers,
            params={
                "jql": f'project={jira_project_key} AND created >= -15m ORDER BY created DESC',
                "maxResults": 10,
                "fields": "summary,created",
            },
        )
        assert resp.status_code == 200, f"Jira search error: {resp.status_code} {resp.text}"
        issues = resp.json().get("issues", [])
        found_key = next(
            (i["key"] for i in issues if f"INC-{incident_number}" in i["fields"]["summary"]),
            None,
        )
        if found_key:
            break
        time.sleep(POLL_INTERVAL)

    assert found_key, f"No Jira ticket found for INC-{incident_number} within {MAX_WAIT}s"
    print(f"✓ Jira ticket found: {found_key} — {jira_site_url}/browse/{found_key}")


# ── 4b: Slack Block Kit message ─────────────────────────────────────────────

def test_slack_incident_message_posted(slack_incidents_channel_id, slack_bot_token):
    client = WebClient(token=slack_bot_token)
    print(f"\nChecking Slack channel {slack_incidents_channel_id} for incident message...")

    deadline = time.time() + MAX_WAIT
    found = False
    while time.time() < deadline:
        history = client.conversations_history(channel=slack_incidents_channel_id, limit=10)
        for msg in history.get("messages", []):
            blocks = msg.get("blocks", [])
            has_section = any(b.get("type") == "section" for b in blocks)
            has_button  = any(
                b.get("type") == "actions" and
                any(e.get("action_id") == "create_war_room" for e in b.get("elements", []))
                for b in blocks
            )
            if has_section and has_button:
                found = True
                break
        if found:
            break
        time.sleep(POLL_INTERVAL)

    assert found, f"No Block Kit incident message with 'Create War Room' button found in channel within {MAX_WAIT}s"
    print("✓ Slack Block Kit message with 'Create War Room' button found")


# ── 4c: Google Meet link in Slack ────────────────────────────────────────────

def test_slack_message_contains_meet_link(slack_incidents_channel_id, slack_bot_token):
    client = WebClient(token=slack_bot_token)
    print(f"\nChecking Slack channel {slack_incidents_channel_id} for meet.google.com link...")

    deadline = time.time() + MAX_WAIT
    found = False
    while time.time() < deadline:
        history = client.conversations_history(channel=slack_incidents_channel_id, limit=10)
        for msg in history.get("messages", []):
            text   = msg.get("text", "")
            blocks = msg.get("blocks", [])
            block_text = " ".join(
                c.get("text", {}).get("text", "")
                for b in blocks
                for c in ([b] if b.get("type") == "section" else [])
            )
            if "meet.google.com" in text or "meet.google.com" in block_text:
                found = True
                break
        if found:
            break
        time.sleep(POLL_INTERVAL)

    assert found, f"No meet.google.com link found in channel messages within {MAX_WAIT}s"
    print("✓ Google Meet link found in Slack message")
