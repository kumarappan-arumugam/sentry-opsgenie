from __future__ import absolute_import

import logging

from sentry import tagstore
from sentry.models import (
    GroupAssignee, User, Team
)
from opsgenie import CreateAlertRequest

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
        return actor.get_display_name()
    if isinstance(actor, Team):
        return actor.slug


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


def build_alert_payload(group, team_id=None, user_id=None, priority=None, event=None, tags=None, identity=None, actions=None, rules=None):

    priority = LEVEL_TO_PRIORITY.get(event.get_tag('level')) if not priority else priority
    description = build_attachment_text(group, event) or ''

    if actions is None:
        actions = []

    assignee = get_assignee(group)

    fields = []

    if tags:
        event_tags = event.tags if event else group.get_latest_event().tags

        for key, value in event_tags:
            std_key = tagstore.get_standardized_key(key)
            if std_key not in tags:
                continue

            labeled_value = tagstore.get_tag_value_label(key, value)
            fields.append('%s:%s' % (std_key.encode('utf-8'), labeled_value.encode('utf-8')))

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
        alias = 'sentry-%d' % group.id,
        description = description,
        responders = [
            {"id": team_id, "type": "team"},
            {"id": user_id, "type": "user"},
        ],
        # actions = ["Restart", "AnExampleAction"],
        tags = fields,
        details = {
            'Assignee': str(assignee),
            'Sentry ID': str(group.id),
            'Sentry Group': getattr(group, 'message_short', group.message).encode('utf-8'),
            'Checksum': group.checksum,
            'Project ID': group.project.slug,
            'Project Name': group.project.name,
            'Logger': group.logger,
            'Level': group.get_level_display(),
            'URL': group.get_absolute_url(params={'referrer': 'opsgenie'}), # don't foget to set system.url-prefix in config.yml
            'Timestamp': str(ts),
            'Trigerring Rules': footer
        },
        entity = group.culprit,
        source = 'Sentry',
        priority = priority
    )
