# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
import uuid

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# JustiFi Terminal API URL
TERMINALS_URL = 'https://api.justifi.ai/v1/terminals'


class PosJustiFiController(http.Controller):
    """Controller for JustiFi POS terminal payments."""

    @http.route('/pos_justifi/payment_request', type='jsonrpc', auth='user', methods=['POST'])
    def payment_request(self, payment_method_id, amount, currency_id, pos_order_id=None):
        """
        Initiate a payment request to a JustiFi terminal.

        This creates a checkout session and sends it to the terminal.

        :param payment_method_id: ID of the pos.payment.method
        :param amount: Payment amount (in currency units, not cents)
        :param currency_id: ID of the currency
        :param pos_order_id: Optional POS order reference
        :return: dict with checkout_id and terminal_action_id for status tracking
        """
        _logger.info(
            "JustiFi POS: Payment request - method=%s, amount=%s, currency=%s, order=%s",
            payment_method_id, amount, currency_id, pos_order_id
        )

        try:
            # Get the payment method and provider
            payment_method = request.env['pos.payment.method'].sudo().browse(payment_method_id)
            if not payment_method.exists():
                return {'error': 'Payment method not found'}

            if payment_method.use_payment_terminal != 'justifi':
                return {'error': 'Invalid payment method type'}

            if not payment_method.justifi_terminal_id:
                return {'error': 'Terminal ID not configured'}

            provider = payment_method.justifi_payment_provider_id
            if not provider or provider.state == 'disabled':
                return {'error': 'JustiFi provider not configured or disabled'}

            # Get currency
            currency = request.env['res.currency'].sudo().browse(currency_id)
            if not currency.exists():
                return {'error': 'Currency not found'}

            # Convert amount to cents
            amount_cents = int(float(amount) * 100)

            # Get base URL for origin
            base_url = provider.get_base_url()

            # Create checkout session
            description = f"POS Payment"
            if pos_order_id:
                description = f"POS Order {pos_order_id}"

            checkout = provider._justifi_create_checkout(
                amount=amount_cents,
                currency=currency.name,
                description=description,
                origin_url=base_url,
            )

            checkout_id = checkout['id']
            _logger.info("JustiFi POS: Checkout created: %s", checkout_id)

            # Send payment to terminal
            terminal_response = self._send_to_terminal(
                provider=provider,
                terminal_id=payment_method.justifi_terminal_id,
                checkout_id=checkout_id,
            )

            # Extract terminal action ID for status polling
            terminal_action_id = terminal_response.get('id', '')

            _logger.info(
                "JustiFi POS: Payment sent to terminal %s, action=%s",
                payment_method.justifi_terminal_id, terminal_action_id
            )

            return {
                'success': True,
                'checkout_id': checkout_id,
                'terminal_action_id': terminal_action_id,
                'terminal_id': payment_method.justifi_terminal_id,
            }

        except Exception as e:
            _logger.exception("JustiFi POS: Error initiating payment: %s", str(e))
            return {'error': str(e)}

    @http.route('/pos_justifi/payment_status', type='jsonrpc', auth='user', methods=['POST'])
    def payment_status(self, checkout_id, terminal_action_id=None):
        """
        Check the status of a terminal payment.

        :param checkout_id: The JustiFi checkout ID
        :param terminal_action_id: Optional terminal action ID
        :return: dict with payment status
        """
        _logger.info("JustiFi POS: Status check - checkout=%s, action=%s", checkout_id, terminal_action_id)

        try:
            # Find the JustiFi provider
            provider = request.env['payment.provider'].sudo().search([
                ('code', '=', 'justifi'),
                ('state', '!=', 'disabled'),
            ], limit=1)

            if not provider:
                return {'error': 'JustiFi provider not found'}

            # Get checkout status
            checkout = provider._justifi_get_checkout(checkout_id)
            status = checkout.get('status', '')
            payment_id = checkout.get('successful_payment_id', '')

            _logger.info("JustiFi POS: Checkout %s status=%s, payment=%s", checkout_id, status, payment_id)

            return {
                'success': True,
                'status': status,
                'payment_id': payment_id,
                'checkout_id': checkout_id,
                'is_paid': status in ('completed', 'succeeded'),
                'is_pending': status in ('pending', 'created'),
                'is_failed': status in ('failed', 'canceled'),
            }

        except Exception as e:
            _logger.exception("JustiFi POS: Error checking status: %s", str(e))
            return {'error': str(e)}

    @http.route('/pos_justifi/cancel_payment', type='jsonrpc', auth='user', methods=['POST'])
    def cancel_payment(self, checkout_id, terminal_id):
        """
        Cancel a pending terminal payment.

        :param checkout_id: The JustiFi checkout ID
        :param terminal_id: The terminal ID
        :return: dict with cancellation result
        """
        _logger.info("JustiFi POS: Cancel request - checkout=%s, terminal=%s", checkout_id, terminal_id)

        try:
            # Find the JustiFi provider
            provider = request.env['payment.provider'].sudo().search([
                ('code', '=', 'justifi'),
                ('state', '!=', 'disabled'),
            ], limit=1)

            if not provider:
                return {'error': 'JustiFi provider not found'}

            # Cancel the terminal action
            result = self._cancel_terminal_action(
                provider=provider,
                terminal_id=terminal_id,
                checkout_id=checkout_id,
            )

            _logger.info("JustiFi POS: Payment cancelled for checkout %s", checkout_id)

            return {
                'success': True,
                'cancelled': True,
            }

        except Exception as e:
            _logger.exception("JustiFi POS: Error cancelling payment: %s", str(e))
            return {'error': str(e)}

    def _send_to_terminal(self, provider, terminal_id, checkout_id):
        """
        Send a checkout to a JustiFi terminal for payment.

        :param provider: The payment.provider record
        :param terminal_id: The terminal ID (trm_xxxxx)
        :param checkout_id: The checkout ID (cho_xxxxx)
        :return: API response dict
        """
        import requests

        access_token = provider._justifi_get_access_token()

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Sub-Account': provider.justifi_account_id,
            'Idempotency-Key': str(uuid.uuid4()),
        }

        url = f'{TERMINALS_URL}/{terminal_id}/pay'
        payload = {
            'checkout_id': checkout_id,
        }

        _logger.info("JustiFi POS: Sending to terminal %s: %s", terminal_id, payload)

        response = requests.post(url, json=payload, headers=headers, timeout=30)

        _logger.info(
            "JustiFi POS: Terminal response: %s %s",
            response.status_code, response.text[:500] if response.text else ''
        )

        if response.status_code >= 400:
            error_msg = "Failed to send payment to terminal"
            try:
                error_data = response.json()
                if 'error' in error_data and 'message' in error_data['error']:
                    error_msg = error_data['error']['message']
            except Exception:
                pass
            raise Exception(error_msg)

        data = response.json()
        return data.get('data', data)

    def _cancel_terminal_action(self, provider, terminal_id, checkout_id):
        """
        Cancel a terminal payment action.

        :param provider: The payment.provider record
        :param terminal_id: The terminal ID
        :param checkout_id: The checkout ID
        :return: API response dict
        """
        import requests

        access_token = provider._justifi_get_access_token()

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Sub-Account': provider.justifi_account_id,
        }

        url = f'{TERMINALS_URL}/{terminal_id}/cancel'
        payload = {
            'checkout_id': checkout_id,
        }

        _logger.info("JustiFi POS: Cancelling terminal %s action for checkout %s", terminal_id, checkout_id)

        response = requests.post(url, json=payload, headers=headers, timeout=30)

        _logger.info(
            "JustiFi POS: Cancel response: %s %s",
            response.status_code, response.text[:200] if response.text else ''
        )

        if response.status_code >= 400:
            _logger.warning("JustiFi POS: Cancel may have failed: %s", response.text)
            # Don't raise - cancellation might fail if payment already completed

        try:
            data = response.json()
            return data.get('data', data)
        except Exception:
            return {}
