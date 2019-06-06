from __future__ import absolute_import

from django import forms
from django.utils.translation import ugettext_lazy as _

from sentry.rules.actions.base import EventAction
from sentry.utils import metrics, json
from sentry.models import Integration

from zenalerts import GetTeamRequest
from zenalerts import GetUserRequest

from .utils import build_alert_payload

class OpsgenieNotifyServiceForm(forms.Form):
    account = forms.ChoiceField(choices=(), widget=forms.Select())
    team = forms.ChoiceField(choices=(), widget=forms.Select())
    username = forms.CharField(widget=forms.TextInput())
    user_id = forms.HiddenInput()
    team_id = forms.HiddenInput()
    priority = forms.ChoiceField(choices=(), widget=forms.Select())
    tags = forms.CharField(required=False, widget=forms.TextInput())

    def __init__(self, *args, **kwargs):
        # NOTE: Account maps directly to the integration ID
        account_list = [(i.id, i.name) for i in kwargs.pop('integrations')]
        self.team_and_or_user_transformer = kwargs.pop('team_and_or_user_transformer')
        # self.get_teams = kwargs.pop('get_teams')
        # self.get_users = kwargs.pop('get_users')

        super(OpsgenieNotifyServiceForm, self).__init__(*args, **kwargs)

        if account_list:
            self.fields['account'].initial = account_list[0][0]

        self.fields['account'].choices = account_list
        self.fields['account'].widget.choices = self.fields['account'].choices

    def clean(self):
        cleaned_data = super(OpsgenieNotifyServiceForm, self).clean()

        account = cleaned_data.get('account')
        team = cleaned_data.get('team', '')
        username = cleaned_data.get('username', '')

        team_id, user_id = self.team_and_or_user_transformer(account, team, username)

        if team and team_id is None and account is not None:
            params = {
                'team': team,
                'account': dict(self.fields['account'].choices).get(int(account)),
            }

            raise forms.ValidationError(
                _('The opsgenie resource "%(team)s" does not exist or has not been granted access in the %(account)s Opsgenie account.'),
                code='invalid',
                params=params,
            )

        if username and user_id is None and account is not None:
            params = {
                'user': user,
                'account': dict(self.fields['account'].choices).get(int(account)),
            }

            raise forms.ValidationError(
                _('The opsgenie resource "%(user)s" does not exist or has not been granted access in the %(account)s Opsgenie account.'),
                code='invalid',
                params=params,
            )

        if team_id:
            cleaned_data['team_id'] = team_id
        if user_id:
            cleaned_data['user_id'] = user_id

        return cleaned_data

class OpsgenieNotifyServiceAction(EventAction):
    form_cls = OpsgenieNotifyServiceForm
    label = u'Send an alert to the {account} Opsgenie account to {team} and(or) {username} and show tags {tags} in alert'

    def __init__(self, *args, **kwargs):
        super(OpsgenieNotifyServiceForm, self).__init__(*args, **kwargs)
        self.form_fields = {
            'account': {
                'type': 'choice',
                'choices': [(i.id, i.name) for i in self.get_integrations()]
            },
            'team': {
                'type': 'string',
                'placeholder': 'i.e Infrastructure'
            },
            'tags': {
                'type': 'string',
                'placeholder': 'i.e environment,user,app_name'
            }
        }

    def is_enabled(self):
        return self.get_integrations().exists()

    def after(self, event, state):
        if event.group.is_ignored():
            return

        integration_id = self.get_option('account')
        team_id = self.get_option('team_id')
        user_id = self.get_option('user_id')
        tags = set(self.get_tags_list())

        try:
            integration = Integration.objects.get(
                provider='opsgenie',
                organizations=self.project.organization,
                id=integration_id
            )
        except Integration.DoesNotExist:
            # Integration removed, rule still active.
            return

        def send_alert(event, futures):
            rules = [f.rule for f in futures]
            payload = build_alert_payload(event.group, team_id, user_id, event=event, tags=tags, rules=rules)

            client = integration.get_installation(organization_id=self.project.organization.id).get_client()

            resp = client.alerts.create_alert(payload)
            if not resp.get('ok'):
                self.logger.info('rule.fail.opsgenie_post', extra={'error': resp.get('message')})

        key = u'opsgenie:{}:{}:{}'.format(integration_id, team_id, user_id)

        metrics.incr('alert.sent', instance='opsgenie.alert', skip_internal=False)
        yield self.future(send_alert, key=key)

    def render_label(self):
        try:
            integration_name = Integration.objects.get(
                provider='opsgenie',
                organizations=self.project.organization,
                id=self.get_option('account')
            ).name
        except Integration.DoesNotExist:
            integration_name = '[removed]'

        tags = self.get_tags_list()

        return self.label.format(
            account=integration_name,
            team=self.get_option('team'),
            username=self.get_option('username'),
            tags=u'[{}]'.format(', '.join(tags)),
        )

    def get_tags_list(self):
        return [s.strip() for s in self.get_option('tags', '').split(',')]

    def get_integrations(self):
        return Integration.objects.filter(
            provider='opsgenie',
            organizations=self.project.organization,
        )

    def get_form_instance(self):
        return self.form_cls(
            self.data,
            integrations=self.get_integrations(),
            team_and_or_user_transformer=self.get_team_and_or_user_id,
        )

    def get_team_and_or_user_id(self, integration_id, team, username):
        try:
            integration = Integration.objects.get(
                provider='opsgenie',
                organizations=self.project.organization,
                id=integration_id,
            )
        except Integration.DoesNotExist:
            return None

        team_id = None
        user_id = None

        client = integration.get_installation(organization_id=self.project.organization.id).get_client()

        try:
            resp = client.teams.get_team(GetTeamRequest(identifier=team, identifierType='name'))
            team_id = resp.id
        except Exception as e:
            self.logger.info('rule.opsgenie.team_list_failed', extra={'error': e.message})

        try:
            resp = client.users.get_user(GetUserRequest(identifier=username))
            user_id = resp.id
        except Exception as e:
            self.logger.info('rule.opsgenie.user_list_failed', extra={'error': e.message})

        return team_id, user_id
