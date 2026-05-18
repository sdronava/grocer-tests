import pulumi
import pulumi_aws as aws


class GrocerVpc:
    def __init__(self, name: str, cidr_block: str = "10.0.0.0/16",
                 tags: dict | None = None, opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.ec2.Vpc(
            f"{name}-vpc",
            cidr_block=cidr_block,
            enable_dns_support=True,
            enable_dns_hostnames=True,
            tags={**(tags or {}), "Name": f"{name}-vpc"},
            opts=opts,
        )

    @property
    def id(self) -> pulumi.Output[str]:
        return self.resource.id


class GrocerInternetGateway:
    def __init__(self, name: str, vpc_id: pulumi.Output[str],
                 tags: dict | None = None, opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.ec2.InternetGateway(
            f"{name}-igw",
            vpc_id=vpc_id,
            tags={**(tags or {}), "Name": f"{name}-igw"},
            opts=opts,
        )

    @property
    def id(self) -> pulumi.Output[str]:
        return self.resource.id


class GrocerSubnet:
    def __init__(self, name: str, vpc_id: pulumi.Output[str],
                 cidr_block: str, availability_zone: str,
                 tags: dict | None = None, opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.ec2.Subnet(
            f"{name}-subnet",
            vpc_id=vpc_id,
            cidr_block=cidr_block,
            availability_zone=availability_zone,
            tags={**(tags or {}), "Name": f"{name}-subnet"},
            opts=opts,
        )

    @property
    def id(self) -> pulumi.Output[str]:
        return self.resource.id


class GrocerEip:
    def __init__(self, name: str, tags: dict | None = None,
                 opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.ec2.Eip(
            f"{name}-eip",
            domain="vpc",
            tags={**(tags or {}), "Name": f"{name}-eip"},
            opts=opts,
        )

    @property
    def id(self) -> pulumi.Output[str]:
        return self.resource.id


class GrocerNatGateway:
    def __init__(self, name: str, subnet_id: pulumi.Output[str],
                 allocation_id: pulumi.Output[str],
                 tags: dict | None = None, opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.ec2.NatGateway(
            f"{name}-nat-gw",
            subnet_id=subnet_id,
            allocation_id=allocation_id,
            tags={**(tags or {}), "Name": f"{name}-nat-gw"},
            opts=opts,
        )

    @property
    def id(self) -> pulumi.Output[str]:
        return self.resource.id


class GrocerRouteTable:
    def __init__(self, name: str, vpc_id: pulumi.Output[str],
                 routes: list,
                 tags: dict | None = None, opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.ec2.RouteTable(
            f"{name}-rt",
            vpc_id=vpc_id,
            routes=routes,
            tags={**(tags or {}), "Name": f"{name}-rt"},
            opts=opts,
        )

    @property
    def id(self) -> pulumi.Output[str]:
        return self.resource.id


class GrocerRouteTableAssociation:
    def __init__(self, name: str, subnet_id: pulumi.Output[str],
                 route_table_id: pulumi.Output[str],
                 opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.ec2.RouteTableAssociation(
            f"{name}-rt-assoc",
            subnet_id=subnet_id,
            route_table_id=route_table_id,
            opts=opts,
        )
