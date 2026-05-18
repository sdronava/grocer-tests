import json

import pulumi
import pulumi_aws as aws


class GrocerSecurityGroup:
    def __init__(self, name: str, vpc_id: pulumi.Output[str],
                 description: str | None = None,
                 ingress: list | None = None,
                 egress: list | None = None,
                 tags: dict | None = None, opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.ec2.SecurityGroup(
            f"{name}-sg",
            vpc_id=vpc_id,
            description=description or f"{name}: egress-only",
            ingress=ingress or [],
            egress=egress or [aws.ec2.SecurityGroupEgressArgs(
                protocol="-1", from_port=0, to_port=0, cidr_blocks=["0.0.0.0/0"],
            )],
            tags={**(tags or {}), "Name": f"{name}-sg"},
            opts=opts,
        )

    @property
    def id(self) -> pulumi.Output[str]:
        return self.resource.id


class GrocerIamRole:
    """IAM role with a single service trust principal and optional managed policy attachments."""

    def __init__(self, name: str, trust_service: str,
                 policy_arns: list[str] | None = None,
                 tags: dict | None = None, opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.iam.Role(
            f"{name}-role",
            assume_role_policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": trust_service},
                    "Action": "sts:AssumeRole",
                }],
            }),
            tags={**(tags or {}), "Name": f"{name}-role"},
            opts=opts,
        )
        for i, arn in enumerate(policy_arns or []):
            aws.iam.RolePolicyAttachment(
                f"{name}-policy" if len(policy_arns or []) == 1 else f"{name}-policy-{i}",
                role=self.resource.name,
                policy_arn=arn,
                opts=opts,
            )

    @property
    def id(self) -> pulumi.Output[str]:
        return self.resource.id

    @property
    def name(self) -> pulumi.Output[str]:
        return self.resource.name


class GrocerInstanceProfile:
    def __init__(self, name: str, role: GrocerIamRole,
                 tags: dict | None = None, opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.iam.InstanceProfile(
            f"{name}-profile",
            role=role.name,
            tags={**(tags or {}), "Name": f"{name}-profile"},
            opts=opts,
        )

    @property
    def name(self) -> pulumi.Output[str]:
        return self.resource.name


class GrocerInstance:
    def __init__(self, name: str,
                 subnet_id: pulumi.Output[str],
                 security_group_ids: list,
                 instance_profile_name: pulumi.Output[str],
                 instance_type: str = "t3.micro",
                 user_data: str = "#!/bin/bash\ndnf install -y stress-ng\n",
                 associate_public_ip_address: bool = False,
                 extra_ebs: list | None = None,
                 tags: dict | None = None, opts: pulumi.ResourceOptions | None = None):
        ami = aws.ec2.get_ami(
            most_recent=True,
            owners=["amazon"],
            filters=[
                aws.ec2.GetAmiFilterArgs(name="name", values=["al2023-ami-*-kernel-6.1-x86_64"]),
                aws.ec2.GetAmiFilterArgs(name="architecture", values=["x86_64"]),
                aws.ec2.GetAmiFilterArgs(name="state", values=["available"]),
            ],
        )
        self.resource = aws.ec2.Instance(
            f"{name}-ec2",
            ami=ami.id,
            instance_type=instance_type,
            subnet_id=subnet_id,
            vpc_security_group_ids=security_group_ids,
            iam_instance_profile=instance_profile_name,
            user_data=user_data,
            associate_public_ip_address=associate_public_ip_address,
            ebs_block_devices=extra_ebs or None,
            tags={**(tags or {}), "Name": f"{name}-ec2"},
            opts=opts,
        )

    @property
    def id(self) -> pulumi.Output[str]:
        return self.resource.id

    @property
    def public_ip(self) -> pulumi.Output[str]:
        return self.resource.public_ip
