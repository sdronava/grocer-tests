from dataclasses import dataclass

import pulumi
import pulumi_aws as aws
from grocer_pulumi_resources import (
    GrocerVpc, GrocerInternetGateway, GrocerSubnet,
    GrocerEip, GrocerNatGateway, GrocerRouteTable, GrocerRouteTableAssociation,
)


@dataclass
class NetworkConfig:
    cidr_block: str = "10.0.0.0/16"
    availability_zone: str = "us-east-1a"
    public_cidr: str = "10.0.1.0/24"
    private_cidr: str = "10.0.2.0/24"


class IsolatedNetwork(pulumi.ComponentResource):
    """
    Self-contained VPC with a private subnet (for workloads) and a public
    subnet hosting a NAT Gateway so private resources have outbound internet
    access (required for SSM agent and SNS HTTPS delivery).
    """

    def __init__(self, name: str, config: NetworkConfig | None = None,
                 tags: dict | None = None, opts: pulumi.ResourceOptions | None = None):
        super().__init__("grocer:networking:IsolatedNetwork", name, None, opts)

        cfg = config or NetworkConfig()
        tags = tags or {}
        co = pulumi.ResourceOptions(parent=self)

        vpc = GrocerVpc(name, cidr_block=cfg.cidr_block, tags=tags, opts=co)
        igw = GrocerInternetGateway(name, vpc_id=vpc.id, tags=tags, opts=co)

        self.public_subnet = GrocerSubnet(
            f"{name}-public", vpc_id=vpc.id, cidr_block=cfg.public_cidr,
            availability_zone=cfg.availability_zone, tags=tags, opts=co,
        )
        self.private_subnet = GrocerSubnet(
            f"{name}-private", vpc_id=vpc.id, cidr_block=cfg.private_cidr,
            availability_zone=cfg.availability_zone, tags=tags, opts=co,
        )

        eip = GrocerEip(name, tags=tags, opts=co)
        nat_gw = GrocerNatGateway(
            name, subnet_id=self.public_subnet.id, allocation_id=eip.id,
            tags=tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[igw.resource]),
        )

        public_rt = GrocerRouteTable(
            f"{name}-public", vpc_id=vpc.id,
            routes=[aws.ec2.RouteTableRouteArgs(cidr_block="0.0.0.0/0", gateway_id=igw.id)],
            tags=tags, opts=co,
        )
        GrocerRouteTableAssociation(
            f"{name}-public", subnet_id=self.public_subnet.id,
            route_table_id=public_rt.id, opts=co,
        )

        private_rt = GrocerRouteTable(
            f"{name}-private", vpc_id=vpc.id,
            routes=[aws.ec2.RouteTableRouteArgs(cidr_block="0.0.0.0/0", nat_gateway_id=nat_gw.id)],
            tags=tags, opts=co,
        )
        GrocerRouteTableAssociation(
            f"{name}-private", subnet_id=self.private_subnet.id,
            route_table_id=private_rt.id, opts=co,
        )

        self.vpc = vpc
        self.nat_gw = nat_gw
        self.register_outputs({
            "vpc_id": vpc.id,
            "public_subnet_id": self.public_subnet.id,
            "private_subnet_id": self.private_subnet.id,
        })
