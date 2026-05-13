# PLAN.md — Test 01: EC2 Incident End-to-End

## Status
- [ ] Plan reviewed and signed off
- [ ] `pulumi preview` reviewed and confirmed clean
- [ ] Infrastructure provisioned (`pulumi up`)
- [ ] Test assertions passed
- [ ] Teardown complete (`pulumi destroy`)
- [ ] AWS console and PagerDuty confirm no orphaned resources
- [ ] Findings committed

---

## 1. Scope

### What this test proves
- An EC2 CPU spike triggers a CloudWatch alarm
- The alarm publishes to SNS
- SNS delivers to PagerDuty Events API v2 via HTTPS subscription
- PagerDuty creates a triggered incident
- The incident can be resolved via PagerDuty Events API v2
- Pulumi can manage all resources end-to-end (AWS + PagerDuty)

### What this test does NOT cover
- EC2 auto-recovery or auto-scaling
- Multi-region alerting
- PagerDuty on-call scheduling beyond a minimal escalation policy
- Sustained load testing or performance benchmarking
- Alert de-duplication or suppression logic

---

## 2. Infrastructure Plan

**Stack name:** `grocer-tests-test01-dev`
**Region:** `us-east-1`

### Networking design

The test provisions its own isolated VPC so it has zero dependency on any pre-existing network infrastructure and tears down completely with `pulumi destroy`.

```
VPC 10.0.0.0/16
├── public subnet  10.0.1.0/24  (us-east-1a)  ← NAT Gateway lives here
└── private subnet 10.0.2.0/24  (us-east-1a)  ← EC2 instance lives here
```

The EC2 instance sits in the **private subnet** (no public IP). The NAT Gateway gives it outbound internet access, which is required for the SSM agent to reach AWS SSM endpoints and for SNS to deliver to PagerDuty via HTTPS.

### PagerDuty Provider Evaluation

`pulumi-pagerduty` (backed by the Terraform PagerDuty provider) supports:
- `pagerduty.EscalationPolicy` — required dependency for a Service
- `pagerduty.Service` — the PagerDuty service that receives alerts
- `pagerduty.ServiceIntegration` — integration on the service (type: `aws_cloudwatch_inbound_integration`)

**Decision: Pulumi-manage all PagerDuty resources.**
The provider is mature and covers everything needed. All PagerDuty resources live in the same stack and are destroyed with `pulumi destroy`.

### Resources

| # | Logical name | Pulumi type | Notes |
|---|---|---|---|
| 1 | `grocer-test01-vpc` | `aws.ec2.Vpc` | CIDR 10.0.0.0/16; DNS support enabled |
| 2 | `grocer-test01-igw` | `aws.ec2.InternetGateway` | Attached to VPC; required for NAT Gateway |
| 3 | `grocer-test01-public-subnet` | `aws.ec2.Subnet` | 10.0.1.0/24, us-east-1a; NAT Gateway resides here |
| 4 | `grocer-test01-private-subnet` | `aws.ec2.Subnet` | 10.0.2.0/24, us-east-1a; EC2 instance resides here |
| 5 | `grocer-test01-eip` | `aws.ec2.Eip` | Elastic IP for the NAT Gateway |
| 6 | `grocer-test01-nat-gw` | `aws.ec2.NatGateway` | In public subnet; routes private subnet egress to internet |
| 7 | `grocer-test01-public-rt` | `aws.ec2.RouteTable` | Default route → IGW |
| 8 | `grocer-test01-public-rt-assoc` | `aws.ec2.RouteTableAssociation` | Associates public subnet with public route table |
| 9 | `grocer-test01-private-rt` | `aws.ec2.RouteTable` | Default route → NAT Gateway |
| 10 | `grocer-test01-private-rt-assoc` | `aws.ec2.RouteTableAssociation` | Associates private subnet with private route table |
| 11 | `grocer-test01-sg` | `aws.ec2.SecurityGroup` | Egress-only; no inbound ports open |
| 12 | `grocer-test01-ssm-role` | `aws.iam.Role` | EC2 service principal; allows SSM Run Command |
| 13 | `grocer-test01-ssm-policy` | `aws.iam.RolePolicyAttachment` | Attaches `AmazonSSMManagedInstanceCore` managed policy |
| 14 | `grocer-test01-ssm-profile` | `aws.iam.InstanceProfile` | Wraps the IAM role; attached to EC2 instance |
| 15 | `grocer-test01-ec2` | `aws.ec2.Instance` | t3.micro, Amazon Linux 2023, private subnet |
| 16 | `grocer-test01-alarm` | `aws.cloudwatch.MetricAlarm` | CPUUtilization ≥ 80% for 1× 1-min period |
| 17 | `grocer-test01-sns` | `aws.sns.Topic` | Receives alarm notifications |
| 18 | `grocer-test01-sns-sub` | `aws.sns.TopicSubscription` | Protocol: https; Endpoint: PagerDuty Events API v2 URL from integration |
| 19 | `grocer-test01-escalation` | `pagerduty.EscalationPolicy` | Single layer, target: configured user ID |
| 20 | `grocer-test01-service` | `pagerduty.Service` | auto_resolve_timeout: 14400s, ack_timeout: 1800s |
| 21 | `grocer-test01-integration` | `pagerduty.ServiceIntegration` | type: `aws_cloudwatch_inbound_integration`; exposes routing key |

**Total: 21 resources**

### Stack outputs (used by test scripts)

| Output key | Value |
|---|---|
| `instance_id` | EC2 instance ID |
| `alarm_name` | CloudWatch alarm name |
| `sns_topic_arn` | SNS topic ARN |
| `pd_service_id` | PagerDuty service ID |
| `pd_integration_key` | PagerDuty routing key (marked secret) |

### IAM / Permissions required

The executing AWS credentials need:
- `ec2:RunInstances`, `ec2:TerminateInstances`, `ec2:Describe*`, `ec2:CreateSecurityGroup`, `ec2:DeleteSecurityGroup`, `ec2:AuthorizeSecurityGroup*`
- `ec2:CreateVpc`, `ec2:DeleteVpc`, `ec2:CreateSubnet`, `ec2:DeleteSubnet`, `ec2:CreateInternetGateway`, `ec2:DeleteInternetGateway`, `ec2:AttachInternetGateway`, `ec2:DetachInternetGateway`
- `ec2:AllocateAddress`, `ec2:ReleaseAddress`, `ec2:CreateNatGateway`, `ec2:DeleteNatGateway`
- `ec2:CreateRouteTable`, `ec2:DeleteRouteTable`, `ec2:CreateRoute`, `ec2:DeleteRoute`, `ec2:AssociateRouteTable`, `ec2:DisassociateRouteTable`
- `iam:CreateRole`, `iam:DeleteRole`, `iam:AttachRolePolicy`, `iam:DetachRolePolicy`, `iam:PassRole`, `iam:CreateInstanceProfile`, `iam:DeleteInstanceProfile`, `iam:AddRoleToInstanceProfile`, `iam:RemoveRoleFromInstanceProfile`, `iam:GetRole`, `iam:GetInstanceProfile`
- `cloudwatch:PutMetricAlarm`, `cloudwatch:DeleteAlarms`, `cloudwatch:Describe*`, `cloudwatch:GetMetricStatistics`
- `sns:CreateTopic`, `sns:DeleteTopic`, `sns:Subscribe`, `sns:Unsubscribe`, `sns:GetTopicAttributes`, `sns:SetTopicAttributes`, `sns:ListSubscriptionsByTopic`
- `ssm:SendCommand`, `ssm:GetCommandInvocation`

SNS → PagerDuty HTTPS delivery requires no additional IAM (public endpoint).

### Config / Secrets setup

```bash
# Run once before pulumi up
pulumi config set aws:profile grocer-sso-admin
pulumi config set aws:region us-east-1
pulumi config set pd_escalation_target_user_id <PD_USER_ID>
pulumi config set --secret pagerduty:token <PD_API_TOKEN>
```

No VPC or subnet IDs needed — all networking is provisioned by this stack.

`PD_USER_ID`: the PagerDuty user ID to assign as the escalation target (find in PagerDuty → User → URL, e.g. `P1ABCDE`). Stored in the project namespace (`grocer-tests-test01:`), not `pagerduty:`, to avoid conflicting with the PagerDuty provider's own config keys.
`PD_API_TOKEN`: a PagerDuty user or service API token with write access to Services. Stored in `pagerduty:token` as the provider expects it there.

---

## 3. Test Logic Plan

### Scripts

| Script | Purpose |
|---|---|
| `scripts/trigger_alarm.py` | Spike CPU on EC2; wait for CloudWatch alarm to enter ALARM state |
| `scripts/verify_incident.py` | Confirm SNS delivery, confirm PD incident triggered, resolve it, confirm resolved |

### Step-by-step

**trigger_alarm.py**

1. Read stack outputs: `instance_id`, `alarm_name` (via `pulumi stack output`).
2. Send SSM Run Command to the instance:
   ```bash
   stress-ng --cpu 0 --timeout 180s
   ```
   (SSM avoids needing an open inbound port; instance needs `AmazonSSMManagedInstanceCore` policy.)
3. Poll `cloudwatch.describe_alarms` every 15 s, timeout 6 min.
4. Assert `StateValue == "ALARM"`; exit non-zero on timeout.

**verify_incident.py**

5. Check SNS delivery health:
   - Query CloudWatch metric `AWS/SNS / NumberOfNotificationsFailed` for the topic over the last 10 minutes.
   - Assert value == 0.
6. Poll PagerDuty REST API v2: `GET /incidents?service_ids[]=<service_id>&statuses[]=triggered`
   - Retry every 10 s, timeout 3 min (SNS → PD latency can be ~30–60 s).
   - Assert at least one incident; capture `incident_id` and `dedup_key`.
7. Resolve via PagerDuty Events API v2:
   - `POST https://events.pagerduty.com/v2/enqueue`
   - Body: `{"routing_key": "<pd_integration_key>", "event_action": "resolve", "dedup_key": "<dedup_key>"}`
   - Assert HTTP 202.
8. Confirm resolution:
   - Poll `GET /incidents/<incident_id>` every 10 s, timeout 60 s.
   - Assert `status == "resolved"`.

### Running tests

```bash
# From tests/test01-ec2-incident/
uv run pytest scripts/ -v

# Or individually
uv run python scripts/trigger_alarm.py
uv run python scripts/verify_incident.py
```

---

## 4. Teardown Plan

### Automated

```bash
# From tests/test01-ec2-incident/
pulumi destroy --yes
```

Pulumi destroys resources in reverse-dependency order:

1. `grocer-test01-integration` (pagerduty.ServiceIntegration)
2. `grocer-test01-service` (pagerduty.Service)
3. `grocer-test01-escalation` (pagerduty.EscalationPolicy)
4. `grocer-test01-sns-sub` (aws.sns.TopicSubscription)
5. `grocer-test01-sns` (aws.sns.Topic)
6. `grocer-test01-alarm` (aws.cloudwatch.MetricAlarm)
7. `grocer-test01-ec2` (aws.ec2.Instance)
8. `grocer-test01-ssm-profile` (aws.iam.InstanceProfile)
9. `grocer-test01-ssm-policy` (aws.iam.RolePolicyAttachment)
10. `grocer-test01-ssm-role` (aws.iam.Role)
11. `grocer-test01-sg` (aws.ec2.SecurityGroup)
12. `grocer-test01-private-rt-assoc` (aws.ec2.RouteTableAssociation)
13. `grocer-test01-private-rt` (aws.ec2.RouteTable)
14. `grocer-test01-public-rt-assoc` (aws.ec2.RouteTableAssociation)
15. `grocer-test01-public-rt` (aws.ec2.RouteTable)
16. `grocer-test01-nat-gw` (aws.ec2.NatGateway — takes ~1 min to delete)
17. `grocer-test01-eip` (aws.ec2.Eip)
18. `grocer-test01-private-subnet` (aws.ec2.Subnet)
19. `grocer-test01-public-subnet` (aws.ec2.Subnet)
20. `grocer-test01-igw` (aws.ec2.InternetGateway)
21. `grocer-test01-vpc` (aws.ec2.Vpc)

> Note: NAT Gateway deletion typically takes 60–90 seconds. `pulumi destroy` waits automatically.

### Post-destroy verification checklist

- [ ] AWS console → EC2: instance in `terminated` state
- [ ] AWS console → VPC: `grocer-test01-vpc` not present
- [ ] AWS console → CloudWatch → Alarms: `grocer-test01-alarm` not present
- [ ] AWS console → SNS → Topics: `grocer-test01-sns` not present
- [ ] PagerDuty → Services: `grocer-test01-service` not listed
- [ ] `pulumi stack` shows 0 resources

### Manual cleanup (if `pulumi destroy` fails mid-way)

Delete in this order:
1. PagerDuty UI: delete integration → delete service → delete escalation policy
2. AWS console: delete SNS subscription → SNS topic
3. AWS console: delete CloudWatch alarm
4. AWS console: terminate EC2 instance (wait for `terminated`)
5. AWS console: delete security group
6. AWS console: delete NAT Gateway (wait for `deleted`)
7. AWS console: release Elastic IP
8. AWS console: delete route tables
9. AWS console: detach and delete Internet Gateway
10. AWS console: delete subnets
11. AWS console: delete VPC

---

## 5. Implementation

> **Do not proceed to this section until the plan above is reviewed and signed off.**

Files to create after sign-off:

```
tests/test01-ec2-incident/
├── PLAN.md                      ← this file
├── __main__.py                  # Pulumi program (all 21 resources)
├── Pulumi.yaml                  # project name: grocer-tests-test01
├── Pulumi.test01-dev.yaml       # stack config: aws:profile, aws:region, pagerduty user ID
├── requirements.txt             # pulumi>=3, pulumi-aws>=7, pulumi-pagerduty>=4
└── scripts/
    ├── trigger_alarm.py
    └── verify_incident.py
```
