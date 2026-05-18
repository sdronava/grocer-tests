import pulumi

from grocer_pulumi_components import IsolatedNetwork, TestInstance

TAGS = {"project": "grocer-tests", "test": "ssm-connect", "managed-by": "pulumi"}

network  = IsolatedNetwork("grocer-ssm", tags=TAGS)
instance = TestInstance(
    "grocer-ssm",
    network=network,
    tags=TAGS,
    depends_on=[network.nat_gw.resource],
)

pulumi.export("instance_id", instance.instance_id)
