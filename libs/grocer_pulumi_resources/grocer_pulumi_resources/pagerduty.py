import pulumi
import pulumi_pagerduty as pagerduty


class GrocerEscalationPolicy:
    def __init__(self, name: str, user_id: str,
                 delay_minutes: int = 30,
                 opts: pulumi.ResourceOptions | None = None):
        self.resource = pagerduty.EscalationPolicy(
            f"{name}-escalation",
            name=f"{name}-escalation",
            num_loops=1,
            rules=[pagerduty.EscalationPolicyRuleArgs(
                escalation_delay_in_minutes=delay_minutes,
                targets=[pagerduty.EscalationPolicyRuleTargetArgs(
                    type="user_reference",
                    id=user_id,
                )],
            )],
            opts=opts,
        )

    @property
    def id(self) -> pulumi.Output[str]:
        return self.resource.id


class GrocerPdService:
    def __init__(self, name: str, escalation_policy_id: pulumi.Output[str],
                 auto_resolve_timeout: str = "14400",
                 ack_timeout: str = "1800",
                 opts: pulumi.ResourceOptions | None = None):
        self.resource = pagerduty.Service(
            f"{name}-service",
            name=f"{name}-service",
            escalation_policy=escalation_policy_id,
            auto_resolve_timeout=auto_resolve_timeout,
            acknowledgement_timeout=ack_timeout,
            alert_creation="create_alerts_and_incidents",
            opts=opts,
        )

    @property
    def id(self) -> pulumi.Output[str]:
        return self.resource.id


class GrocerPdIntegration:
    def __init__(self, name: str, service_id: pulumi.Output[str],
                 opts: pulumi.ResourceOptions | None = None):
        cloudwatch_vendor = pagerduty.get_vendor(name="CloudWatch")
        self.resource = pagerduty.ServiceIntegration(
            f"{name}-integration",
            name=f"{name}-cloudwatch",
            service=service_id,
            vendor=cloudwatch_vendor.id,
            opts=opts,
        )

    @property
    def integration_key(self) -> pulumi.Output[str]:
        return self.resource.integration_key
