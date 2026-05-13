# CLAUDE.md — grocer-tests

## Project Overview

**grocer-tests** is a learning sandbox for experimenting with an AWS "grocer" account. Each test is a fully self-contained unit: it can be created, exercised, and torn down independently without touching any other test or shared infrastructure.

---

## Environment & Tooling

| Tool | Role |
|---|---|
| Python | Primary language for all Pulumi programs and test scripts |
| AWS | Cloud provider (grocer account) |
| Pulumi (Python) | Infrastructure as Code — provision and destroy per-test stacks |
| uv | Python package/environment manager (replaces pip/venv) |
| PagerDuty | Alerting/incident platform (account pre-exists) |

---

## Core Principles

### 1. Plan Before Execute
**Always generate and review a plan before running anything that creates, modifies, or destroys real resources.**

- For Pulumi: always run `pulumi preview` and confirm the diff looks correct before `pulumi up`.
- For scripts: document the intended side-effects in a comment block at the top of the file before running.
- For destructive operations: explicitly list what will be deleted in the plan step.

### 2. Incremental Work, Documented in Markdown
Each test is developed and delivered in increments. Every increment must be documented in a Markdown file inside the test folder **before** code is written.

Typical increment breakdown:
1. **Scope** — what the test proves, what it does not cover
2. **Infrastructure plan** — list of resources to create (with Pulumi stack name)
3. **Test logic plan** — step-by-step description of what the test script does
4. **Teardown plan** — how resources are destroyed and verified gone
5. **Implementation** — code written after the above three are reviewed

### 3. Full Isolation Per Test
- Each test has its own Pulumi stack (e.g., `grocer-tests-test01-dev`).
- Tests share no state, no resources, and no Pulumi state files with each other.
- Tests must be runnable (and destroyable) in any order.

---

## Repository Layout

```
grocer-tests/
├── CLAUDE.md                  # ← this file
├── README.md                  # human-readable project intro
├── .python-version            # managed by uv
├── pyproject.toml             # shared dev dependencies (pytest, boto3, etc.)
│
└── tests/
    └── test01-ec2-incident/   # Test 1: EC2 → CloudWatch → SNS → PagerDuty
        ├── PLAN.md            # increment plan (written first, always)
        ├── __main__.py        # Pulumi program
        ├── Pulumi.yaml
        ├── Pulumi.test01-dev.yaml
        ├── requirements.txt   # Pulumi stack deps (managed by uv)
        └── scripts/
            ├── trigger_alarm.py
            └── verify_incident.py
```

Add future tests as `tests/test02-*/`, `tests/test03-*/`, etc.

---

## Workflow — Standard Steps for Any Test

```
1. Create tests/testNN-<name>/PLAN.md
   └── Document: scope, infra plan, test logic, teardown plan

2. Review PLAN.md  ← human sign-off before writing code

3. Write Pulumi program (__main__.py) and test scripts

4. pulumi preview            ← verify diff; do not proceed if unexpected
5. pulumi up --yes           ← provision

6. Run test scripts
   └── pytest scripts/ -v   (or run directly with uv run python scripts/...)

7. pulumi destroy --yes      ← tear down all resources
8. Verify in AWS console / PagerDuty that resources are gone

9. Commit: code + PLAN.md + any notes/findings
```

---

## Test Catalogue

### Test 01 — EC2 Incident End-to-End
**Folder:** `tests/test01-ec2-incident/`
**Plan file:** `tests/test01-ec2-incident/PLAN.md`

**Goal:** Prove the full alert pipeline from an EC2 metric anomaly through to a PagerDuty incident being created and then resolved.

**Resources provisioned by Pulumi:**
- EC2 instance (t3.micro, Amazon Linux 2023)
- CloudWatch Alarm (CPUUtilization threshold)
- SNS Topic + HTTPS subscription pointing at PagerDuty Events API v2
- PagerDuty Service (if `pulumi-pagerduty` provider supports it — evaluate at plan stage)
- PagerDuty Integration on that service (CloudWatch integration type)

**Test steps (scripted):**
1. Artificially spike CPU on the EC2 instance to breach the CloudWatch threshold
2. Wait for alarm state to transition to `ALARM` (poll with boto3)
3. Confirm SNS message was delivered (CloudWatch SNS delivery metrics)
4. Confirm PagerDuty incident is `triggered` via PagerDuty REST API
5. Resolve the incident via PagerDuty Events API v2
6. Confirm incident state is `resolved`

**Teardown:** `pulumi destroy` removes all AWS resources. PagerDuty service (if Pulumi-managed) is also destroyed; otherwise document the manual cleanup step in PLAN.md.

---

## Pulumi Conventions

- Stack naming: `grocer-tests-<testNN>-<env>` (e.g., `grocer-tests-test01-dev`)
- Always tag every resource with:
  ```python
  tags={"project": "grocer-tests", "test": "test01", "managed-by": "pulumi"}
  ```
- Store secrets (PagerDuty routing key, etc.) in Pulumi config as encrypted secrets:
  ```bash
  pulumi config set --secret pagerduty:token <value>
  ```
- Never hardcode credentials or routing keys in source files.

---

## Python & uv Conventions

- Use `uv` for all dependency management — no bare `pip install`.
- Each Pulumi stack has its own `requirements.txt`; sync with:
  ```bash
  uv pip sync requirements.txt
  ```
- Shared dev tooling (pytest, boto3 for test scripts) lives in the root `pyproject.toml`.
- Python version pinned in `.python-version` at repo root.

---

## AWS Account Notes

- Account alias: grocer (learning/sandbox — not production)
- Default region: document in each test's `Pulumi.<stack>.yaml` under `aws:region`
- IAM: use least-privilege per-test roles where practical; document required permissions in PLAN.md

---

## PagerDuty Notes

- Account pre-exists; do not create or delete the top-level account via Pulumi.
- Services and integrations **may** be Pulumi-managed (evaluate `pulumi-pagerduty` provider at Test 01 plan stage).
- If a resource is not Pulumi-managed, document the manual setup steps in the test's PLAN.md and add a teardown checklist.
- PagerDuty API token stored as a Pulumi secret; never committed to source.

---

## Definition of Done (per test)

- [ ] PLAN.md written and reviewed before any code
- [ ] `pulumi preview` output reviewed and confirmed clean
- [ ] Infrastructure provisions successfully (`pulumi up`)
- [ ] All test assertions pass
- [ ] `pulumi destroy` completes with zero resources remaining
- [ ] AWS console and PagerDuty confirm no orphaned resources
- [ ] Code, PLAN.md, and findings committed to repo