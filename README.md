# Sentry Opsgenie

Plugin for Sentry which allows sending notification via  [Opsgenie](https://www.opsgenie.com) service.

## Installation

1.  Install this package
	`pip install https://github.com/kumarappan-arumugam/sentry-opsgenie/archive/<version>.zip`
2.  Restart your Sentry service.
3.  Go to your Sentry web interface. Open  organization `Settings`  page.
4.  On  `Integrations`, find  `Opsgneie`  plugin and install it.
5.  Configure plugin on  `Configure plugin`  page.
    See  [Opsgenie's documentation](https://docs.opsgenie.com/docs/sentry-integration)  to know how to create  `API key`.
    *Note*: Documentation for sentry configuration on opsgenie page is for [legacy integration](https://help.sentry.io/hc/en-us/articles/360003063454-What-are-Global-versus-Legacy-integrations).
6.  Done!
