from __future__ import absolute_import

from zenalerts import ZenAlerts
from zenalerts import Configuration

class OpsgenieClient:

    def __init__(self, api_key, api_url=None):
        self.api_key = api_key
        self.api_url = api_url
        config = Configuration(apikey=api_key)
        self.client = ZenAlerts(config)
