from dataclasses import dataclass

import pulumi
from grocer_pulumi_resources import GrocerSnsTopic, GrocerSnsSubscription, GrocerMetricAlarm

from .compute import TestInstance
from .pagerduty import PagerDutyService


@dataclass
class AlarmConfig:
    metric_name: str = "CPUUtilization"
    namespace: str = "AWS/EC2"
    threshold: float = 80.0
    period: int = 60
    evaluation_periods: int = 1
    statistic: str = "Average"
    comparison_operator: str = "GreaterThanOrEqualToThreshold"


class AlertPipeline(pulumi.ComponentResource):
    """
    CloudWatch alarm → SNS topic → PagerDuty HTTPS subscription.
    Fires when the alarm breaches and resolves when it recovers.
    """

    def __init__(self, name: str, instance: TestInstance, pd_service: PagerDutyService,
                 config: AlarmConfig | None = None,
                 tags: dict | None = None, opts: pulumi.ResourceOptions | None = None):
        super().__init__("grocer:alerting:AlertPipeline", name, None, opts)

        cfg = config or AlarmConfig()
        tags = tags or {}
        co = pulumi.ResourceOptions(parent=self)

        self._topic = GrocerSnsTopic(name, tags=tags, opts=co)

        GrocerSnsSubscription(
            name,
            topic_arn=self._topic.arn,
            protocol="https",
            endpoint=pd_service.integration_key.apply(
                lambda key: f"https://events.pagerduty.com/adapter/cloudwatch_sns/v1/{key}"
            ),
            opts=co,
        )

        self._alarm = GrocerMetricAlarm(
            name,
            metric_name=cfg.metric_name,
            namespace=cfg.namespace,
            dimensions={"InstanceId": instance.instance_id},
            alarm_actions=[self._topic.arn],
            ok_actions=[self._topic.arn],
            threshold=cfg.threshold,
            period=cfg.period,
            evaluation_periods=cfg.evaluation_periods,
            statistic=cfg.statistic,
            comparison_operator=cfg.comparison_operator,
            tags=tags,
            opts=co,
        )

        self.register_outputs({
            "alarm_name": self._alarm.name,
            "sns_topic_arn": self._topic.arn,
        })

    @property
    def alarm_name(self) -> pulumi.Output[str]:
        return self._alarm.name

    @property
    def sns_topic_arn(self) -> pulumi.Output[str]:
        return self._topic.arn
