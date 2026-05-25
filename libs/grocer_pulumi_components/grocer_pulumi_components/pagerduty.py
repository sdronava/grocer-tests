import pulumi
from grocer_pulumi_resources import GrocerEscalationPolicy, GrocerPdService, GrocerPdIntegration


class PagerDutyService(pulumi.ComponentResource):
    """
    PagerDuty escalation policy + service + CloudWatch integration.
    Exposes the integration key needed to wire up an SNS subscription.
    """

    def __init__(self, name: str, user_id: str,
                 auto_resolve_timeout: str = "14400",
                 ack_timeout: str = "1800",
                 opts: pulumi.ResourceOptions | None = None):
        super().__init__("grocer:pagerduty:PagerDutyService", name, None, opts)

        co = pulumi.ResourceOptions(parent=self)

        escalation = GrocerEscalationPolicy(name, user_id=user_id, opts=co)
        self._service = GrocerPdService(
            name,
            escalation_policy_id=escalation.id,
            auto_resolve_timeout=auto_resolve_timeout,
            ack_timeout=ack_timeout,
            opts=co,
        )
        self._integration = GrocerPdIntegration(name, service_id=self._service.id, opts=co)

        self.register_outputs({
            "service_id": self._service.id,
            "integration_key": self._integration.integration_key,
        })

    @property
    def service_id(self) -> pulumi.Output[str]:
        return self._service.id

    @property
    def integration_key(self) -> pulumi.Output[str]:
        return self._integration.integration_key
