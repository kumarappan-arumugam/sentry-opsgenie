from __future__ import absolute_import

import logging

from sentry import tagstore
from sentry.api.fields.actor import Actor
from sentry.utils import json
from sentry.utils.assets import get_asset_url
from sentry.utils.dates import to_timestamp
from sentry.utils.http import absolute_uri
from sentry.models import (
    GroupStatus, GroupAssignee, OrganizationMember, User, Identity, Team,
    Release
)
from zenalerts import CreateAlertRequest

logger = logging.getLogger('sentry.integrations.opsgenie')

LEVEL_TO_PRIORITY = {
    'debug': 'P5',
    'info': 'P4',
    'warning': 'P3',
    'error': 'P2',
    'fatal': 'P1',
}


def format_actor_option(actor):
    if isinstance(actor, User):
        return {'text': actor.get_display_name(), 'value': u'user:{}'.format(actor.id)}
    if isinstance(actor, Team):
        return {'text': u'#{}'.format(actor.slug), 'value': u'team:{}'.format(actor.id)}

    raise NotImplementedError


def get_member_assignees(group):
    queryset = OrganizationMember.objects.filter(
        user__is_active=True,
        organization=group.organization,
        teams__in=group.project.teams.all(),
    ).distinct().select_related('user')

    members = sorted(queryset, key=lambda u: u.user.get_display_name())

    return [format_actor_option(u.user) for u in members]


def get_team_assignees(group):
    return [format_actor_option(u) for u in group.project.teams.all()]


def get_assignee(group):
    try:
        assigned_actor = GroupAssignee.objects.get(group=group).assigned_actor()
    except GroupAssignee.DoesNotExist:
        return None

    try:
        return format_actor_option(assigned_actor.resolve())
    except assigned_actor.type.DoesNotExist:
        return None


def build_attachment_title(group, event=None):
    # This is all super event specific and ideally could just use a
    # combination of `group.title` and `group.title + group.culprit`.
    ev_metadata = group.get_event_metadata()
    ev_type = group.get_event_type()
    if ev_type == 'error':
        if 'type' in ev_metadata:
            if group.culprit:
                return u'{} - {}'.format(ev_metadata['type'][:40], group.culprit)
            return ev_metadata['type']
        if group.culprit:
            return u'{} - {}'.format(group.title, group.culprit)
        return group.title
    elif ev_type == 'csp':
        return u'{} - {}'.format(ev_metadata['directive'], ev_metadata['uri'])
    else:
        if group.culprit:
            return u'{} - {}'.format(group.title[:40], group.culprit)
        return group.title


def build_attachment_text(group, event=None):
    # Group and Event both implement get_event_{type,metadata}
    obj = event if event is not None else group
    ev_metadata = obj.get_event_metadata()
    ev_type = obj.get_event_type()

    if ev_type == 'error':
        return ev_metadata.get('value') or ev_metadata.get('function')
    else:
        return None


def build_assigned_text(group, identity, assignee):
    actor = Actor.from_actor_id(assignee)

    try:
        assigned_actor = actor.resolve()
    except actor.type.DoesNotExist:
        return

    if actor.type == Team:
        assignee_text = u'#{}'.format(assigned_actor.slug)
    elif actor.type == User:
        try:
            assignee_ident = Identity.objects.get(
                user=assigned_actor,
                idp__type='opsgenie',
                idp__external_id=identity.idp.external_id,
            )
            assignee_text = u'<@{}>'.format(assignee_ident.external_id)
        except Identity.DoesNotExist:
            assignee_text = assigned_actor.get_display_name()
    else:
        raise NotImplementedError

    return u'*Issue assigned to {assignee_text} by <@{user_id}>*'.format(
        assignee_text=assignee_text,
        user_id=identity.external_id,
    )


def build_action_text(group, identity, action):
    if action['name'] == 'assign':
        return build_assigned_text(group, identity, action['selected_options'][0]['value'])

    statuses = {
        'resolved': 'resolved',
        'ignored': 'ignored',
        'unresolved': 're-opened',
    }

    # Resolve actions have additional 'parameters' after ':'
    status = action['value'].split(':', 1)[0]

    # Action has no valid action text, ignore
    if status not in statuses:
        return

    return u'*Issue {status} by <@{user_id}>*'.format(
        status=statuses[status],
        user_id=identity.external_id,
    )


def build_alert_payload(group, team_id=None, user_id=None, priority=None, event=None, tags=None, identity=None, actions=None, rules=None):
    status = group.get_status()

    members = get_member_assignees(group)
    teams = get_team_assignees(group)

    priority = LEVEL_TO_PRIORITY.get(event.get_tag('level')) if not priority else priority

    description = build_attachment_text(group, event) or ''

    if actions is None:
        actions = []

    assignee = get_assignee(group)

    # resolve_button = {
    #     'name': 'resolve_dialog',
    #     'value': 'resolve_dialog',
    #     'type': 'button',
    #     'text': 'Resolve...',
    # }

    # ignore_button = {
    #     'name': 'status',
    #     'value': 'ignored',
    #     'type': 'button',
    #     'text': 'Ignore',
    # }

    # has_releases = Release.objects.filter(
    #     projects=group.project,
    #     organization_id=group.project.organization_id
    # ).exists()

    # if not has_releases:
    #     resolve_button.update({
    #         'name': 'status',
    #         'text': 'Resolve',
    #         'value': 'resolved',
    #     })

    # if status == GroupStatus.RESOLVED:
    #     resolve_button.update({
    #         'name': 'status',
    #         'text': 'Unresolve',
    #         'value': 'unresolved',
    #     })

    # if status == GroupStatus.IGNORED:
    #     ignore_button.update({
    #         'text': 'Stop Ignoring',
    #         'value': 'unresolved',
    #     })

    # option_groups = []

    # if teams:
    #     option_groups.append({
    #         'text': 'Teams',
    #         'options': teams,
    #     })

    # if members:
    #     option_groups.append({
    #         'text': 'People',
    #         'options': members,
    #     })

    # payload_actions = [
    #     resolve_button,
    #     ignore_button,
    #     {
    #         'name': 'assign',
    #         'text': 'Select Assignee...',
    #         'type': 'select',
    #         'selected_options': [assignee],
    #         'option_groups': option_groups,
    #     },
    # ]

    fields = []

    if tags:
        event_tags = event.tags if event else group.get_latest_event().tags

        for key, value in event_tags:
            std_key = tagstore.get_standardized_key(key)
            if std_key not in tags:
                continue

            labeled_value = tagstore.get_tag_value_label(key, value)
            fields.append('%s:%s' % (std_key.encode('utf-8'), labeled_value.encode('utf-8')))

    if actions:
        action_texts = filter(None, [build_action_text(group, identity, a) for a in actions])
        text += '\n' + '\n'.join(action_texts)
        payload_actions = []

    ts = group.last_seen

    if event:
        event_ts = event.datetime
        ts = max(ts, event_ts)

    footer = u'{}'.format(group.qualified_short_id)

    if rules:
        footer += u' via {}'.format(rules[0].label)

        if len(rules) > 1:
            footer += u' (+{} other)'.format(len(rules) - 1)

    return CreateAlertRequest(
        message = build_attachment_title(group, event),
        alias = 'sentry: %d' % group.id,
        description = description,
        responders = [
            {"id": team_id, "type": "team"},
            {"id": user_id, "type": "user"},
        ],
        # actions = ["Restart", "AnExampleAction"],
        tags = fields,
        details = {
            'Sentry ID': str(group.id),
            'Sentry Group': getattr(group, 'message_short', group.message).encode('utf-8'),
            'Checksum': group.checksum,
            'Project ID': group.project.slug,
            'Project Name': group.project.name,
            'Logger': group.logger,
            'Level': group.get_level_display(),
            'URL': group.get_absolute_url(params={'referrer': 'opsgenie'}),
            'Timestamp': str(ts),
            'Trigerring Rules': footer
        },
        entity = group.culprit,
        source = 'Sentry',
        priority = priority
    )
