import pulumi
import pulumi_aws as aws


class GrocerCognitoUserPool:
    def __init__(self, name: str, tags: dict | None = None,
                 opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.cognito.UserPool(
            f"{name}-user-pool",
            name=f"{name}-user-pool",
            tags={**(tags or {}), "Name": f"{name}-user-pool"},
            opts=opts,
        )

    @property
    def id(self) -> pulumi.Output[str]:
        return self.resource.id

    @property
    def arn(self) -> pulumi.Output[str]:
        return self.resource.arn

    @property
    def endpoint(self) -> pulumi.Output[str]:
        return self.resource.endpoint


class GrocerCognitoResourceServer:
    """Defines the API's custom OAuth2 scopes inside a User Pool."""

    def __init__(self, name: str,
                 user_pool_id: pulumi.Output[str],
                 identifier: str,
                 scopes: list[dict],
                 opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.cognito.ResourceServer(
            f"{name}-resource-server",
            user_pool_id=user_pool_id,
            identifier=identifier,
            name=f"{name}-resource-server",
            scopes=[
                aws.cognito.ResourceServerScopeArgs(
                    scope_name=s["scope_name"],
                    scope_description=s["scope_description"],
                )
                for s in scopes
            ],
            opts=opts,
        )

    @property
    def scope_identifiers(self) -> pulumi.Output[list]:
        return self.resource.scope_identifiers


class GrocerCognitoUserPoolClient:
    """App client with client_credentials flow enabled."""

    def __init__(self, name: str,
                 user_pool_id: pulumi.Output[str],
                 allowed_oauth_scopes: pulumi.Output[list],
                 opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.cognito.UserPoolClient(
            f"{name}-client",
            name=f"{name}-client",
            user_pool_id=user_pool_id,
            generate_secret=True,
            allowed_oauth_flows=["client_credentials"],
            allowed_oauth_flows_user_pool_client=True,
            allowed_oauth_scopes=allowed_oauth_scopes,
            explicit_auth_flows=[],
            opts=opts,
        )

    @property
    def id(self) -> pulumi.Output[str]:
        return self.resource.id

    @property
    def client_secret(self) -> pulumi.Output[str]:
        return self.resource.client_secret


class GrocerCognitoUserPoolDomain:
    """Hosts the /oauth2/token endpoint at <prefix>.auth.<region>.amazoncognito.com."""

    def __init__(self, name: str,
                 domain_prefix: str,
                 user_pool_id: pulumi.Output[str],
                 opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.cognito.UserPoolDomain(
            f"{name}-domain",
            domain=domain_prefix,
            user_pool_id=user_pool_id,
            opts=opts,
        )

    @property
    def domain(self) -> pulumi.Output[str]:
        return self.resource.domain
