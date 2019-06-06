from __future__ import absolute_import, print_function

from sentry import analytics


class OpsgenieIntegrationAssign(analytics.Event):
    type = 'integrations.opsgenie.assign'

    attributes = (
        analytics.Attribute('actor_id', required=False),
    )


class OpsgenieIntegrationStatus(analytics.Event):
    type = 'integrations.opsgenie.status'

    attributes = (
        analytics.Attribute('status'),
        analytics.Attribute('resolve_type', required=False),
        analytics.Attribute('actor_id', required=False),
    )


analytics.register(OpsgenieIntegrationAssign)
analytics.register(OpsgenieIntegrationStatus)
