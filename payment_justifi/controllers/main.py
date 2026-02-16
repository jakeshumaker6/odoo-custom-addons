# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hashlib
import hmac
import json
import logging

from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class JustiFiController(http.Controller):
    """Controller for JustiFi payment provider."""

    _return_url = '/payment/justifi/return'
    _webhook_url = '/payment/justifi/webhook'
    _complete_url = '/payment/justifi/complete'

    @http.route(_return_url, type='http', auth='public', methods=['GET'], csrf=False)
    def justifi_return(self, **kwargs):
        """
        Handle return from JustiFi payment.

        This is called when the customer is redirected back after payment.
        The actual payment status is handled via webhook or the complete endpoint.

        :return: Redirect to payment status page
        """
        _logger.info("JustiFi: Return endpoint called with data: %s", kwargs)

        # Redirect to the payment status page
        return request.redirect('/payment/status')

    @http.route(_complete_url, type='http', auth='public', methods=['POST'], csrf=False, save_session=False)
    def justifi_complete(self, **kwargs):
        """
        Handle payment completion from the frontend.

        Called by JavaScript when JustiFi modular checkout fires submit-event.

        Expected form data:
        - checkout_id: The JustiFi checkout ID
        - payment_id: The successful payment ID from submit-event

        :return: Redirect to payment status page
        """
        _logger.info("JustiFi: Complete endpoint called with: %s", kwargs)

        try:
            checkout_id = kwargs.get('checkout_id')
            payment_id = kwargs.get('payment_id')

            if not checkout_id:
                _logger.error("JustiFi: Missing checkout_id")
                return request.redirect('/payment/status')

            # Find the transaction by checkout_id (stored in provider_reference)
            tx = request.env['payment.transaction'].sudo().search([
                ('provider_reference', '=', checkout_id),
            ], limit=1)

            if not tx:
                _logger.error("JustiFi: Transaction not found for checkout_id=%s", checkout_id)
                return request.redirect('/payment/status')

            # Get the checkout status from JustiFi to verify
            provider = tx.provider_id
            try:
                checkout_data = provider._justifi_get_checkout(checkout_id)
            except ValidationError as e:
                _logger.error("JustiFi: Failed to verify checkout: %s", str(e))
                return request.redirect('/payment/status')

            # Process the payment data
            checkout_data['checkout_id'] = checkout_id
            if payment_id:
                checkout_data['successful_payment_id'] = payment_id

            tx._justifi_process_payment_data(checkout_data)

            _logger.info("JustiFi: Payment completed for transaction %s", tx.reference)

            return request.redirect('/payment/status')

        except Exception as e:
            _logger.exception("JustiFi: Error in complete endpoint: %s", str(e))
            return request.redirect('/payment/status')

    @http.route(_webhook_url, type='json', auth='public', methods=['POST'], csrf=False)
    def justifi_webhook(self, **kwargs):
        """
        Handle webhooks from JustiFi.

        JustiFi sends webhooks for various payment events:
        - payment.succeeded
        - payment.failed
        - checkout.completed

        :return: HTTP response
        """
        _logger.info("JustiFi: Webhook received")

        try:
            data = request.jsonrequest
            _logger.info("JustiFi: Webhook data: %s", json.dumps(data, indent=2))

            event_type = data.get('event_type', '')
            event_data = data.get('data', {})

            # Get signature from headers for verification
            signature = request.httprequest.headers.get('Justifi-Signature', '')

            # Find the provider to get webhook secret
            provider = request.env['payment.provider'].sudo().search([
                ('code', '=', 'justifi'),
                ('state', '!=', 'disabled'),
            ], limit=1)

            if not provider:
                _logger.error("JustiFi: No active JustiFi provider found")
                return {'status': 'error', 'message': 'Provider not found'}

            # Verify webhook signature if secret is configured
            if provider.justifi_webhook_secret and signature:
                if not self._verify_webhook_signature(
                    request.httprequest.data,
                    signature,
                    provider.justifi_webhook_secret
                ):
                    _logger.error("JustiFi: Invalid webhook signature")
                    return {'status': 'error', 'message': 'Invalid signature'}

            # Process based on event type
            if event_type in ('payment.succeeded', 'checkout.completed'):
                self._handle_payment_success(provider, event_data)
            elif event_type == 'payment.failed':
                self._handle_payment_failure(provider, event_data)
            else:
                _logger.info("JustiFi: Unhandled event type: %s", event_type)

            return {'status': 'ok'}

        except Exception as e:
            _logger.exception("JustiFi: Error processing webhook: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    def _verify_webhook_signature(self, payload, signature, secret):
        """
        Verify the webhook signature.

        :param payload: Raw request body
        :param signature: Signature from headers
        :param secret: Webhook secret
        :return: True if valid, False otherwise
        """
        if isinstance(payload, bytes):
            payload = payload.decode('utf-8')

        expected = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    def _handle_payment_success(self, provider, event_data):
        """
        Handle successful payment webhook.

        :param provider: The payment provider
        :param event_data: The event data from webhook
        """
        checkout_id = event_data.get('id', '')
        payment_id = event_data.get('successful_payment_id', '')

        _logger.info(
            "JustiFi: Processing payment success webhook: checkout=%s, payment=%s",
            checkout_id, payment_id
        )

        # Find the transaction
        tx = None
        if checkout_id:
            tx = request.env['payment.transaction'].sudo().search([
                ('provider_reference', '=', checkout_id),
                ('provider_id', '=', provider.id),
            ], limit=1)

        if not tx and payment_id:
            tx = request.env['payment.transaction'].sudo().search([
                ('provider_reference', '=', payment_id),
                ('provider_id', '=', provider.id),
            ], limit=1)

        if tx:
            # Only process if not already done
            if tx.state not in ('done', 'cancel'):
                event_data['status'] = 'completed'
                event_data['checkout_id'] = checkout_id
                tx._justifi_process_payment_data(event_data)
                _logger.info("JustiFi: Transaction %s marked as done via webhook", tx.reference)
        else:
            _logger.warning(
                "JustiFi: Transaction not found for webhook: checkout=%s, payment=%s",
                checkout_id, payment_id
            )

    def _handle_payment_failure(self, provider, event_data):
        """
        Handle failed payment webhook.

        :param provider: The payment provider
        :param event_data: The event data from webhook
        """
        checkout_id = event_data.get('id', '')
        error_message = event_data.get('error', {}).get('message', 'Payment failed')

        _logger.info("JustiFi: Processing payment failure webhook: checkout=%s", checkout_id)

        # Find the transaction
        tx = request.env['payment.transaction'].sudo().search([
            ('provider_reference', '=', checkout_id),
            ('provider_id', '=', provider.id),
        ], limit=1)

        if tx and tx.state not in ('done', 'cancel'):
            event_data['status'] = 'failed'
            event_data['checkout_id'] = checkout_id
            tx._justifi_process_payment_data(event_data)
            _logger.info("JustiFi: Transaction %s marked as failed via webhook", tx.reference)
