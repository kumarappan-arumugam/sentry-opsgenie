from __future__ import absolute_import, print_function

from django.core.urlresolvers import reverse
from django.db import IntegrityError
from django.http import Http404
from django.utils import timezone
from django.views.decorators.cache import never_cache

from sentry import http
from sentry.models import Integration, Identity, IdentityProvider, IdentityStatus, Organization
from sentry.utils.http import absolute_uri
from sentry.utils.signing import sign, unsign
from sentry.web.frontend.base import BaseView
from sentry.web.helpers import render_to_response

from .utils import logger


def build_linking_url(integration, organization, opsgenie_id, channel_id, response_url):
    signed_params = sign(
        integration_id=integration.id,
        organization_id=organization.id,
        opsgenie_id=opsgenie_id,
        channel_id=channel_id,
        response_url=response_url,
    )

    return absolute_uri(reverse('sentry-integration-opsgenie-link-identity', kwargs={
        'signed_params': signed_params,
    }))


class OpsgenieLinkIdentitiyView(BaseView):
    @never_cache
    def handle(self, request, signed_params):
        params = unsign(signed_params.encode('ascii', errors='ignore'))

        try:
            organization = Organization.objects.get(
                id__in=request.user.get_orgs(),
                id=params['organization_id'],
            )
        except Organization.DoesNotExist:
            raise Http404

        try:
            integration = Integration.objects.get(
                id=params['integration_id'],
                organizations=organization,
            )
        except Integration.DoesNotExist:
            raise Http404

        try:
            idp = IdentityProvider.objects.get(
                external_id=integration.external_id,
                type='opsgenie',
            )
        except IdentityProvider.DoesNotExist:
            raise Http404

        if request.method != 'POST':
            return render_to_response('sentry/auth-link-identity.html', request=request, context={
                'organization': organization,
                'provider': integration.get_provider(),
            })

        # Link the user with the identity. Handle the case where the user is linked to a
        # different identity or the identity is linked to a different user.
        defaults = {
            'status': IdentityStatus.VALID,
            'date_verified': timezone.now(),
        }
        try:
            identity, created = Identity.objects.get_or_create(
                idp=idp,
                user=request.user,
                external_id=params['opsgenie_user_id'],
                defaults=defaults,
            )
            if not created:
                identity.update(**defaults)
        except IntegrityError:
            Identity.reattach(idp, params['opsgenie_user_id'], request.user, defaults)

        payload = {
            'replace_original': False,
            'response_type': 'ephemeral',
            'text': "Your Opsgenie identity has been linked to your Sentry account. You're good to go!"
        }

        session = http.build_session()
        req = session.post(params['response_url'], json=payload)
        resp = req.json()

        # If the user took their time to link their opsgenie account, we may no
        # longer be able to respond, and we're not guaranteed able to post into
        # the channel. Ignore Expired url errors.
        #
        if not resp.get('ok') and resp.get('error') != 'Expired url':
            logger.error('opsgenie.link-notify.response-error', extra={'response': resp})

        return render_to_response('sentry/opsgenie-linked.html', request=request, context={
            'channel_id': params['channel_id'],
            'team_id': integration.external_id,
        })
