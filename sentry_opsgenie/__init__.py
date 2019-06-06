from __future__ import absolute_import

from sentry.utils.imports import import_submodules
from sentry.rules import rules
from sentry.integrations import register

from .notify_action import OpsgenieNotifyServiceAction
from .integration import OpsgenieIntegrationProvider

import_submodules(globals(), __name__, __path__)

rules.add(OpsgenieNotifyServiceAction)
register(OpsgenieIntegrationProvider)
