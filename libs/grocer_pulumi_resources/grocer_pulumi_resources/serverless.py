import pulumi
import pulumi_aws as aws


class GrocerLambdaFunction:
    def __init__(self, name: str,
                 handler: str,
                 runtime: str,
                 code: pulumi.Archive,
                 role_arn: pulumi.Output[str],
                 timeout: int = 30,
                 memory_size: int = 128,
                 environment: dict | None = None,
                 tags: dict | None = None,
                 opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.lambda_.Function(
            f"{name}-lambda",
            name=f"{name}-lambda",
            runtime=runtime,
            handler=handler,
            code=code,
            role=role_arn,
            timeout=timeout,
            memory_size=memory_size,
            environment=aws.lambda_.FunctionEnvironmentArgs(
                variables=environment
            ) if environment else None,
            tags={**(tags or {}), "Name": f"{name}-lambda"},
            opts=opts,
        )

    @property
    def arn(self) -> pulumi.Output[str]:
        return self.resource.arn

    @property
    def invoke_arn(self) -> pulumi.Output[str]:
        return self.resource.invoke_arn

    @property
    def name(self) -> pulumi.Output[str]:
        return self.resource.name


class GrocerLambdaPermission:
    def __init__(self, name: str,
                 function_name: pulumi.Output[str],
                 principal: str,
                 source_arn: pulumi.Output[str],
                 opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.lambda_.Permission(
            f"{name}-lambda-perm",
            action="lambda:InvokeFunction",
            function=function_name,
            principal=principal,
            source_arn=source_arn,
            opts=opts,
        )


class GrocerHttpApi:
    def __init__(self, name: str,
                 tags: dict | None = None,
                 opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.apigatewayv2.Api(
            f"{name}-api",
            name=f"{name}-api",
            protocol_type="HTTP",
            tags={**(tags or {}), "Name": f"{name}-api"},
            opts=opts,
        )

    @property
    def id(self) -> pulumi.Output[str]:
        return self.resource.id

    @property
    def execution_arn(self) -> pulumi.Output[str]:
        return self.resource.execution_arn


class GrocerHttpApiIntegration:
    def __init__(self, name: str,
                 api_id: pulumi.Output[str],
                 integration_uri: pulumi.Output[str],
                 opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.apigatewayv2.Integration(
            f"{name}-integration",
            api_id=api_id,
            integration_type="AWS_PROXY",
            integration_uri=integration_uri,
            payload_format_version="2.0",
            opts=opts,
        )

    @property
    def id(self) -> pulumi.Output[str]:
        return self.resource.id


class GrocerHttpApiRoute:
    def __init__(self, name: str,
                 api_id: pulumi.Output[str],
                 route_key: str,
                 integration_id: pulumi.Output[str],
                 opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.apigatewayv2.Route(
            f"{name}-route",
            api_id=api_id,
            route_key=route_key,
            target=integration_id.apply(lambda i: f"integrations/{i}"),
            opts=opts,
        )


class GrocerHttpApiStage:
    def __init__(self, name: str,
                 api_id: pulumi.Output[str],
                 stage_name: str = "$default",
                 auto_deploy: bool = True,
                 access_log_destination_arn: pulumi.Output[str] | None = None,
                 access_log_format: str | None = None,
                 tags: dict | None = None,
                 opts: pulumi.ResourceOptions | None = None):
        access_log_settings = None
        if access_log_destination_arn is not None:
            access_log_settings = aws.apigatewayv2.StageAccessLogSettingsArgs(
                destination_arn=access_log_destination_arn,
                format=access_log_format or (
                    '{"requestId":"$context.requestId"'
                    ',"sourceIp":"$context.identity.sourceIp"'
                    ',"userAgent":"$context.identity.userAgent"'
                    ',"requestTime":"$context.requestTime"'
                    ',"httpMethod":"$context.httpMethod"'
                    ',"routeKey":"$context.routeKey"'
                    ',"status":"$context.status"'
                    ',"responseLength":"$context.responseLength"'
                    ',"integrationLatency":$context.integrationLatency'
                    ',"responseLatency":$context.responseLatency}'
                ),
            )
        self.resource = aws.apigatewayv2.Stage(
            f"{name}-stage",
            api_id=api_id,
            name=stage_name,
            auto_deploy=auto_deploy,
            access_log_settings=access_log_settings,
            tags={**(tags or {}), "Name": f"{name}-stage"},
            opts=opts,
        )

    @property
    def invoke_url(self) -> pulumi.Output[str]:
        return self.resource.invoke_url
