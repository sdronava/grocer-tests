import pulumi
import pulumi_aws as aws
from grocer_pulumi_resources import (
    GrocerIamRole,
    GrocerLambdaFunction, GrocerLambdaPermission,
    GrocerHttpApi, GrocerHttpApiIntegration, GrocerHttpApiRoute, GrocerHttpApiStage,
)


class ApiGatewayLambda(pulumi.ComponentResource):
    """
    HTTP API Gateway wired to a single Lambda function.
    Creates: IAM role, Lambda, HTTP API, integration, route, stage, resource policy.
    Exposes endpoint_url = stage invoke URL + route path.
    """

    def __init__(self, name: str,
                 handler: str,
                 runtime: str,
                 code: pulumi.Archive,
                 route_key: str = "GET /invoke",
                 timeout: int = 30,
                 memory_size: int = 128,
                 environment: dict | None = None,
                 tags: dict | None = None,
                 opts: pulumi.ResourceOptions | None = None):
        super().__init__("grocer:apigateway:ApiGatewayLambda", name, None, opts)

        tags = tags or {}
        co = pulumi.ResourceOptions(parent=self)

        role = GrocerIamRole(
            name,
            trust_service="lambda.amazonaws.com",
            policy_arns=["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"],
            tags=tags,
            opts=co,
        )

        fn = GrocerLambdaFunction(
            name,
            handler=handler,
            runtime=runtime,
            code=code,
            role_arn=role.arn,
            timeout=timeout,
            memory_size=memory_size,
            environment=environment,
            tags=tags,
            opts=co,
        )

        api = GrocerHttpApi(name, tags=tags, opts=co)

        log_group = aws.cloudwatch.LogGroup(
            f"{name}-access-logs",
            name=f"/aws/apigateway/{name}",
            retention_in_days=1,
            tags={**tags, "Name": f"{name}-access-logs"},
            opts=co,
        )

        integration = GrocerHttpApiIntegration(
            name,
            api_id=api.id,
            integration_uri=fn.invoke_arn,
            opts=co,
        )

        GrocerHttpApiRoute(
            name,
            api_id=api.id,
            route_key=route_key,
            integration_id=integration.id,
            opts=co,
        )

        stage = GrocerHttpApiStage(
            name,
            api_id=api.id,
            access_log_destination_arn=log_group.arn,
            tags=tags,
            opts=co,
        )

        GrocerLambdaPermission(
            name,
            function_name=fn.name,
            principal="apigateway.amazonaws.com",
            source_arn=api.execution_arn.apply(lambda arn: f"{arn}/*/*"),
            opts=co,
        )

        route_path = route_key.split(" ")[1]
        self._endpoint_url = stage.invoke_url.apply(lambda url: url + route_path)
        self._log_group_name = log_group.name

        self.register_outputs({
            "endpoint_url": self._endpoint_url,
            "log_group_name": self._log_group_name,
        })

    @property
    def endpoint_url(self) -> pulumi.Output[str]:
        return self._endpoint_url

    @property
    def log_group_name(self) -> pulumi.Output[str]:
        return self._log_group_name
