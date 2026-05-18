from dataclasses import dataclass, field

import pulumi
import pulumi_aws as aws
from grocer_pulumi_resources import (
    GrocerSecurityGroup, GrocerIamRole, GrocerInstanceProfile, GrocerInstance,
)

from .networking import IsolatedNetwork


@dataclass
class EBSVolumeConfig:
    size_gb: int
    device_name: str
    volume_type: str = "gp3"


@dataclass
class InstanceConfig:
    instance_type: str = "t3.micro"
    # Default installs stress-ng so CPU spike tests work out of the box.
    # Override for tests that need different instance setup.
    user_data: str = "#!/bin/bash\ndnf install -y stress-ng\n"
    extra_ebs: list[EBSVolumeConfig] = field(default_factory=list)


class TestInstance(pulumi.ComponentResource):
    """
    EC2 instance in the private subnet with an SSM instance profile
    (no inbound ports, no public IP). Optionally attaches extra EBS volumes.
    """

    def __init__(self, name: str, network: IsolatedNetwork,
                 config: InstanceConfig | None = None,
                 tags: dict | None = None,
                 public: bool = False,
                 allow_ssh: bool = False,
                 depends_on: list | None = None,
                 opts: pulumi.ResourceOptions | None = None):
        super().__init__("grocer:compute:TestInstance", name, None, opts)

        cfg = config or InstanceConfig()
        tags = tags or {}
        co = pulumi.ResourceOptions(parent=self)
        instance_co = pulumi.ResourceOptions(parent=self, depends_on=depends_on or [])

        ingress = []
        if allow_ssh:
            ingress = [aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp", from_port=22, to_port=22, cidr_blocks=["0.0.0.0/0"],
            )]

        sg = GrocerSecurityGroup(name, vpc_id=network.vpc.id, ingress=ingress, tags=tags, opts=co)

        role = GrocerIamRole(
            f"{name}-ssm",
            trust_service="ec2.amazonaws.com",
            policy_arns=["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"],
            tags=tags,
            opts=co,
        )
        profile = GrocerInstanceProfile(f"{name}-ssm", role=role, tags=tags, opts=co)

        ebs_mappings = [
            aws.ec2.InstanceEbsBlockDeviceArgs(
                device_name=vol.device_name,
                volume_size=vol.size_gb,
                volume_type=vol.volume_type,
            )
            for vol in cfg.extra_ebs
        ] or None

        subnet_id = network.public_subnet.id if public else network.private_subnet.id

        self._instance = GrocerInstance(
            name,
            subnet_id=subnet_id,
            security_group_ids=[sg.id],
            instance_profile_name=profile.name,
            instance_type=cfg.instance_type,
            user_data=cfg.user_data,
            associate_public_ip_address=public,
            extra_ebs=ebs_mappings,
            tags=tags,
            opts=instance_co,
        )

        self.register_outputs({
            "instance_id": self._instance.id,
            "public_ip": self._instance.public_ip,
        })

    @property
    def instance_id(self) -> pulumi.Output[str]:
        return self._instance.id

    @property
    def public_ip(self) -> pulumi.Output[str]:
        return self._instance.public_ip
