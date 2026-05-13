import json
import pulumi
import pulumi_aws as aws
import pulumi_pagerduty as pagerduty

config = pulumi.Config()
pd_user_id = config.require("pd_escalation_target_user_id")

TAGS = {"project": "grocer-tests", "test": "test01", "managed-by": "pulumi"}

# --- AMI: latest Amazon Linux 2023 x86_64 ---

ami = aws.ec2.get_ami(
    most_recent=True,
    owners=["amazon"],
    filters=[
        aws.ec2.GetAmiFilterArgs(name="name", values=["al2023-ami-*-x86_64"]),
        aws.ec2.GetAmiFilterArgs(name="architecture", values=["x86_64"]),
        aws.ec2.GetAmiFilterArgs(name="state", values=["available"]),
    ],
)

# --- VPC ---

vpc = aws.ec2.Vpc(
    "grocer-test01-vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_support=True,
    enable_dns_hostnames=True,
    tags={**TAGS, "Name": "grocer-test01-vpc"},
)

igw = aws.ec2.InternetGateway(
    "grocer-test01-igw",
    vpc_id=vpc.id,
    tags={**TAGS, "Name": "grocer-test01-igw"},
)

# Public subnet — NAT Gateway resides here
public_subnet = aws.ec2.Subnet(
    "grocer-test01-public-subnet",
    vpc_id=vpc.id,
    cidr_block="10.0.1.0/24",
    availability_zone="us-east-1a",
    tags={**TAGS, "Name": "grocer-test01-public-subnet"},
)

# Private subnet — EC2 instance resides here (no public IP)
private_subnet = aws.ec2.Subnet(
    "grocer-test01-private-subnet",
    vpc_id=vpc.id,
    cidr_block="10.0.2.0/24",
    availability_zone="us-east-1a",
    tags={**TAGS, "Name": "grocer-test01-private-subnet"},
)

# NAT Gateway (in public subnet) gives private subnet outbound internet access
# Required for SSM agent to reach AWS endpoints and SNS to deliver to PagerDuty
eip = aws.ec2.Eip(
    "grocer-test01-eip",
    domain="vpc",
    tags={**TAGS, "Name": "grocer-test01-eip"},
)

nat_gw = aws.ec2.NatGateway(
    "grocer-test01-nat-gw",
    subnet_id=public_subnet.id,
    allocation_id=eip.id,
    tags={**TAGS, "Name": "grocer-test01-nat-gw"},
    opts=pulumi.ResourceOptions(depends_on=[igw]),
)

# Public route table: default route → IGW
public_rt = aws.ec2.RouteTable(
    "grocer-test01-public-rt",
    vpc_id=vpc.id,
    routes=[aws.ec2.RouteTableRouteArgs(
        cidr_block="0.0.0.0/0",
        gateway_id=igw.id,
    )],
    tags={**TAGS, "Name": "grocer-test01-public-rt"},
)

aws.ec2.RouteTableAssociation(
    "grocer-test01-public-rt-assoc",
    subnet_id=public_subnet.id,
    route_table_id=public_rt.id,
)

# Private route table: default route → NAT Gateway
private_rt = aws.ec2.RouteTable(
    "grocer-test01-private-rt",
    vpc_id=vpc.id,
    routes=[aws.ec2.RouteTableRouteArgs(
        cidr_block="0.0.0.0/0",
        nat_gateway_id=nat_gw.id,
    )],
    tags={**TAGS, "Name": "grocer-test01-private-rt"},
)

aws.ec2.RouteTableAssociation(
    "grocer-test01-private-rt-assoc",
    subnet_id=private_subnet.id,
    route_table_id=private_rt.id,
)

# --- Security group: egress-only ---

sg = aws.ec2.SecurityGroup(
    "grocer-test01-sg",
    vpc_id=vpc.id,
    description="grocer-test01: egress-only",
    egress=[aws.ec2.SecurityGroupEgressArgs(
        protocol="-1",
        from_port=0,
        to_port=0,
        cidr_blocks=["0.0.0.0/0"],
    )],
    tags={**TAGS, "Name": "grocer-test01-sg"},
)

# --- IAM role + instance profile for SSM Run Command ---

ssm_role = aws.iam.Role(
    "grocer-test01-ssm-role",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "ec2.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    }),
    tags={**TAGS, "Name": "grocer-test01-ssm-role"},
)

aws.iam.RolePolicyAttachment(
    "grocer-test01-ssm-policy",
    role=ssm_role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
)

ssm_profile = aws.iam.InstanceProfile(
    "grocer-test01-ssm-profile",
    role=ssm_role.name,
    tags={**TAGS, "Name": "grocer-test01-ssm-profile"},
)

# --- EC2 instance (private subnet, no public IP) ---
# User data installs stress-ng so it is ready when the test script runs.

instance = aws.ec2.Instance(
    "grocer-test01-ec2",
    ami=ami.id,
    instance_type="t3.micro",
    subnet_id=private_subnet.id,
    vpc_security_group_ids=[sg.id],
    iam_instance_profile=ssm_profile.name,
    user_data="#!/bin/bash\ndnf install -y stress-ng\n",
    tags={**TAGS, "Name": "grocer-test01-ec2"},
)

# --- PagerDuty: escalation policy → service → CloudWatch integration ---

escalation = pagerduty.EscalationPolicy(
    "grocer-test01-escalation",
    name="grocer-test01-escalation",
    num_loops=1,
    rules=[pagerduty.EscalationPolicyRuleArgs(
        escalation_delay_in_minutes=30,
        targets=[pagerduty.EscalationPolicyRuleTargetArgs(
            type="user_reference",
            id=pd_user_id,
        )],
    )],
)

service = pagerduty.Service(
    "grocer-test01-service",
    name="grocer-test01-service",
    escalation_policy=escalation.id,
    auto_resolve_timeout="14400",
    acknowledgement_timeout="1800",
    alert_creation="create_alerts_and_incidents",
)

cloudwatch_vendor = pagerduty.get_vendor(name="CloudWatch")

integration = pagerduty.ServiceIntegration(
    "grocer-test01-integration",
    name="grocer-test01-cloudwatch",
    service=service.id,
    vendor=cloudwatch_vendor.id,
)

# --- SNS topic + HTTPS subscription to PagerDuty ---

sns_topic = aws.sns.Topic(
    "grocer-test01-sns",
    tags={**TAGS, "Name": "grocer-test01-sns"},
)

aws.sns.TopicSubscription(
    "grocer-test01-sns-sub",
    topic=sns_topic.arn,
    protocol="https",
    endpoint=integration.integration_key.apply(
        lambda key: f"https://events.pagerduty.com/adapter/cloudwatch_sns/v1/{key}"
    ),
)

# --- CloudWatch alarm ---

alarm = aws.cloudwatch.MetricAlarm(
    "grocer-test01-alarm",
    name="grocer-test01-alarm",
    comparison_operator="GreaterThanOrEqualToThreshold",
    evaluation_periods=1,
    metric_name="CPUUtilization",
    namespace="AWS/EC2",
    period=60,
    statistic="Average",
    threshold=80.0,
    alarm_description="grocer-test01: CPU spike test alarm",
    dimensions={"InstanceId": instance.id},
    alarm_actions=[sns_topic.arn],
    ok_actions=[sns_topic.arn],
    treat_missing_data="notBreaching",
    tags={**TAGS, "Name": "grocer-test01-alarm"},
)

# --- Stack outputs for test scripts ---

pulumi.export("instance_id", instance.id)
pulumi.export("alarm_name", alarm.name)
pulumi.export("sns_topic_arn", sns_topic.arn)
pulumi.export("pd_service_id", service.id)
pulumi.export("pd_integration_key", pulumi.Output.secret(integration.integration_key))
