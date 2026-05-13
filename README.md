# grocer-tests

Learning sandbox for experimenting with AWS (grocer account).

Each test is fully self-contained — create, exercise, and tear down independently.

## Tests

| Test | Folder | Description |
|---|---|---|
| 01 | `tests/test01-ec2-incident/` | EC2 CPU spike → CloudWatch → SNS → PagerDuty incident |

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/) installed
- [Pulumi CLI](https://www.pulumi.com/docs/install/) installed
- AWS CLI configured with SSO profile `grocer-sso-admin` (see `~/.aws/config`)
- PagerDuty user API token and your PagerDuty user ID

---

## One-time setup

### 1. Authenticate with AWS SSO

```bash
aws sso login --profile grocer-sso-admin
```

Re-run this whenever your SSO session expires (typically every 8 hours).

### 2. Log in to Pulumi state backend

Pulumi state for this project is stored in a dedicated prefix in the shared S3 bucket:

```bash
pulumi login s3://grocer-pulumi-state/grocer-tests
```

Run this once per terminal session (or add `PULUMI_BACKEND_URL=s3://grocer-pulumi-state/grocer-tests` to your shell profile to make it permanent).

---

## Initializing a test stack

Steps below use Test 01 as the example. Repeat the pattern for future tests.

### 1. Install dependencies

```bash
cd tests/test01-ec2-incident/
uv pip sync requirements.txt
```

### 2. Create the stack

```bash
pulumi stack init grocer-tests-test01-dev
```

### 3. Set stack config

```bash
pulumi config set aws:profile grocer-sso-admin
pulumi config set aws:region us-east-1
pulumi config set pd_escalation_target_user_id <PD_USER_ID>
```

`PD_USER_ID`: the alphanumeric ID from your PagerDuty profile URL (e.g. `P1ABCDE`). This is stored in the project namespace to avoid conflicting with the PagerDuty provider's own config keys.

No VPC or subnet IDs needed — the stack provisions its own isolated VPC, public/private subnets, and NAT Gateway.

### 4. Set the PagerDuty token as an encrypted secret

```bash
pulumi config set --secret pagerduty:token <PD_API_TOKEN>
```

This is stored encrypted in the stack state — never committed to source in plaintext.

---

## Running a test

```bash
# Preview infrastructure changes before applying
pulumi preview

# Provision
pulumi up --yes

# Export PagerDuty token for test scripts (verify_incident.py reads this)
export PAGERDUTY_TOKEN=$(pulumi config get pagerduty:token)

# Run test scripts (trigger_alarm first, then verify_incident — alphabetical order)
uv run pytest scripts/ -v -s

# Tear down
pulumi destroy --yes
```

See each test's `PLAN.md` for the full test walkthrough and post-destroy verification checklist.

---

## Switching between projects

This repo uses `s3://grocer-pulumi-state/grocer-tests` as its state backend. The `grocer-platform` project uses `s3://grocer-pulumi-state` (bucket root). If you work on both, remember to `pulumi login` to the right prefix when switching:

```bash
# grocer-tests
pulumi login s3://grocer-pulumi-state/grocer-tests

# grocer-platform
pulumi login s3://grocer-pulumi-state
```
