import pulumi
import pulumi_aws as aws


class GrocerSnsTopic:
    def __init__(self, name: str, tags: dict | None = None,
                 opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.sns.Topic(
            f"{name}-sns",
            tags={**(tags or {}), "Name": f"{name}-sns"},
            opts=opts,
        )

    @property
    def arn(self) -> pulumi.Output[str]:
        return self.resource.arn


class GrocerSnsSubscription:
    def __init__(self, name: str, topic_arn: pulumi.Output[str],
                 protocol: str, endpoint: pulumi.Output[str],
                 opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.sns.TopicSubscription(
            f"{name}-sns-sub",
            topic=topic_arn,
            protocol=protocol,
            endpoint=endpoint,
            opts=opts,
        )


class GrocerMetricAlarm:
    def __init__(self, name: str,
                 metric_name: str,
                 namespace: str,
                 dimensions: dict,
                 alarm_actions: list,
                 ok_actions: list,
                 threshold: float = 80.0,
                 period: int = 60,
                 evaluation_periods: int = 1,
                 statistic: str = "Average",
                 comparison_operator: str = "GreaterThanOrEqualToThreshold",
                 tags: dict | None = None,
                 opts: pulumi.ResourceOptions | None = None):
        self.resource = aws.cloudwatch.MetricAlarm(
            f"{name}-alarm",
            name=f"{name}-alarm",
            comparison_operator=comparison_operator,
            evaluation_periods=evaluation_periods,
            metric_name=metric_name,
            namespace=namespace,
            period=period,
            statistic=statistic,
            threshold=threshold,
            alarm_description=f"{name}: {metric_name} threshold alarm",
            dimensions=dimensions,
            alarm_actions=alarm_actions,
            ok_actions=ok_actions,
            treat_missing_data="notBreaching",
            tags={**(tags or {}), "Name": f"{name}-alarm"},
            opts=opts,
        )

    @property
    def name(self) -> pulumi.Output[str]:
        return self.resource.name
