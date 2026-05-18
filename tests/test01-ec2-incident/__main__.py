import pulumi

from grocer_pulumi_components import (
    IsolatedNetwork,
    TestInstance,
    PagerDutyService,
    AlertPipeline,
)

config = pulumi.Config()
pd_user_id = config.require("pd_escalation_target_user_id")

TAGS = {"project": "grocer-tests", "test": "test01", "managed-by": "pulumi"}

network  = IsolatedNetwork("grocer-test01", tags=TAGS)
instance = TestInstance("grocer-test01", network=network, tags=TAGS)
pd       = PagerDutyService("grocer-test01", user_id=pd_user_id)
alerts   = AlertPipeline("grocer-test01", instance=instance, pd_service=pd, tags=TAGS)

pulumi.export("instance_id",       instance.instance_id)
pulumi.export("alarm_name",        alerts.alarm_name)
pulumi.export("sns_topic_arn",     alerts.sns_topic_arn)
pulumi.export("pd_service_id",     pd.service_id)
pulumi.export("pd_integration_key", pulumi.Output.secret(pd.integration_key))
