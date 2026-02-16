# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import requests

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from ..const import (
    OAUTH_TOKEN_URL,
    CHECKOUTS_URL,
    WEB_COMPONENT_TOKEN_URL,
    SUPPORTED_CURRENCIES,
    PAYMENT_METHOD_CODES,
)

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('justifi', 'JustiFi')],
        ondelete={'justifi': 'set default'},
    )

    # JustiFi-specific configuration fields
    justifi_client_id = fields.Char(
        string="Client ID",
        help="Your JustiFi Client ID from the Developer > API Keys section.",
        required_if_provider='justifi',
        groups='base.group_system',
    )
    justifi_client_secret = fields.Char(
        string="Client Secret",
        help="Your JustiFi Client Secret from the Developer > API Keys section.",
        required_if_provider='justifi',
        groups='base.group_system',
    )
    justifi_account_id = fields.Char(
        string="Sub-Account ID",
        help="Your JustiFi Sub-Account ID (starts with acc_). Required for processing payments.",
        required_if_provider='justifi',
        groups='base.group_system',
    )
    justifi_payment_method_group_id = fields.Char(
        string="Payment Method Group ID",
        help="Your JustiFi Payment Method Group ID (starts with pmg_).",
        groups='base.group_system',
    )
    justifi_webhook_secret = fields.Char(
        string="Webhook Secret",
        help="Your JustiFi Webhook Secret for signature verification.",
        groups='base.group_system',
    )

    # === CONSTRAINT METHODS ===#

    @api.constrains('justifi_account_id')
    def _check_justifi_account_id(self):
        for provider in self:
            if provider.code == 'justifi' and provider.justifi_account_id:
                if not provider.justifi_account_id.startswith('acc_'):
                    raise ValidationError(_(
                        "The Sub-Account ID should start with 'acc_'. "
                        "Please check your JustiFi dashboard for the correct ID."
                    ))

    @api.constrains('justifi_payment_method_group_id')
    def _check_justifi_payment_method_group_id(self):
        for provider in self:
            if provider.code == 'justifi' and provider.justifi_payment_method_group_id:
                if not provider.justifi_payment_method_group_id.startswith('pmg_'):
                    raise ValidationError(_(
                        "The Payment Method Group ID should start with 'pmg_'. "
                        "Please check your JustiFi dashboard for the correct ID."
                    ))

    # === COMPUTE METHODS ===#

    def _compute_feature_support_fields(self):
        """ Override to enable features for JustiFi. """
        super()._compute_feature_support_fields()
        for provider in self.filtered(lambda p: p.code == 'justifi'):
            provider.support_tokenization = False  # Not implementing saved cards initially
            provider.support_manual_capture = False
            provider.support_express_checkout = False
            provider.support_refund = False  # Can be added later

    # === BUSINESS METHODS ===#

    def _get_supported_currencies(self):
        """ Override to return JustiFi's supported currencies. """
        if self.code == 'justifi':
            return self.env['res.currency'].search([('name', 'in', SUPPORTED_CURRENCIES)])
        return super()._get_supported_currencies()

    def _get_default_payment_method_codes(self):
        """ Override to return JustiFi's default payment method codes. """
        if self.code == 'justifi':
            return PAYMENT_METHOD_CODES
        return super()._get_default_payment_method_codes()

    def _should_build_inline_form(self, is_validation=False):
        """ Override to indicate that JustiFi uses an inline form. """
        if self.code == 'justifi':
            return True
        return super()._should_build_inline_form(is_validation=is_validation)

    # === JUSTIFI API METHODS ===#

    def _justifi_get_access_token(self):
        """
        Get OAuth access token from JustiFi API.

        :return: Access token string
        :raises ValidationError: If authentication fails
        """
        self.ensure_one()

        if not self.justifi_client_id or not self.justifi_client_secret:
            raise ValidationError(_("JustiFi Client ID and Client Secret are required."))

        _logger.info("JustiFi: Requesting access token")

        try:
            response = requests.post(
                OAUTH_TOKEN_URL,
                json={
                    'client_id': self.justifi_client_id,
                    'client_secret': self.justifi_client_secret,
                },
                headers={'Content-Type': 'application/json'},
                timeout=30,
            )
        except requests.exceptions.RequestException as e:
            _logger.error("JustiFi: Network error getting access token: %s", str(e))
            raise ValidationError(_("Could not connect to JustiFi. Please try again later."))

        if response.status_code != 200:
            _logger.error(
                "JustiFi: Failed to get access token. Status: %s, Response: %s",
                response.status_code, response.text
            )
            raise ValidationError(_("JustiFi authentication failed. Please check your credentials."))

        data = response.json()
        access_token = data.get('access_token')

        if not access_token:
            _logger.error("JustiFi: No access token in response: %s", data)
            raise ValidationError(_("JustiFi authentication failed. No access token received."))

        _logger.info("JustiFi: Access token obtained successfully")
        return access_token

    def _justifi_create_checkout(self, amount, currency, description, origin_url):
        """
        Create a checkout session with JustiFi.

        :param amount: Amount in cents (integer)
        :param currency: Currency code (e.g., 'usd')
        :param description: Payment description
        :param origin_url: Origin URL for the web component
        :return: Checkout data dict with 'id' key
        :raises ValidationError: If checkout creation fails
        """
        self.ensure_one()

        access_token = self._justifi_get_access_token()

        if not self.justifi_account_id:
            raise ValidationError(_("JustiFi Sub-Account ID is required."))

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Sub-Account': self.justifi_account_id,
        }

        checkout_data = {
            'amount': amount,
            'currency': currency.lower(),
            'description': description,
            'origin_url': origin_url,
        }

        # Add payment method group ID if configured
        if self.justifi_payment_method_group_id:
            checkout_data['payment_method_group_id'] = self.justifi_payment_method_group_id

        _logger.info("JustiFi: Creating checkout with data: %s", checkout_data)

        try:
            response = requests.post(
                CHECKOUTS_URL,
                json=checkout_data,
                headers=headers,
                timeout=30,
            )
        except requests.exceptions.RequestException as e:
            _logger.error("JustiFi: Network error creating checkout: %s", str(e))
            raise ValidationError(_("Could not connect to JustiFi. Please try again later."))

        if response.status_code >= 400:
            _logger.error(
                "JustiFi: Failed to create checkout. Status: %s, Response: %s",
                response.status_code, response.text
            )
            error_msg = "Failed to create checkout"
            try:
                error_data = response.json()
                if 'error' in error_data and 'message' in error_data['error']:
                    error_msg = error_data['error']['message']
            except Exception:
                pass
            raise ValidationError(_("JustiFi: %s") % error_msg)

        data = response.json()
        checkout = data.get('data', data)

        if not checkout.get('id'):
            _logger.error("JustiFi: No checkout ID in response: %s", data)
            raise ValidationError(_("JustiFi: No checkout ID returned."))

        _logger.info("JustiFi: Checkout created: %s", checkout['id'])
        return checkout

    def _justifi_get_web_component_token(self, checkout_id):
        """
        Get a web component token for the frontend.

        Note: This request does NOT include the Sub-Account header.
        The checkout already has sub-account context.

        :param checkout_id: The checkout ID to authorize
        :return: Web component token string
        :raises ValidationError: If token request fails
        """
        self.ensure_one()

        access_token = self._justifi_get_access_token()

        # Build resources array - checkout AND tokenize permissions required
        resources = [
            f'write:checkout:{checkout_id}',
            f'write:tokenize:{self.justifi_account_id}',
        ]

        # Note: Sub-Account header is NOT included here - causes auth failures
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        _logger.info("JustiFi: Requesting web component token for checkout: %s", checkout_id)

        try:
            response = requests.post(
                WEB_COMPONENT_TOKEN_URL,
                json={'resources': resources},
                headers=headers,
                timeout=30,
            )
        except requests.exceptions.RequestException as e:
            _logger.error("JustiFi: Network error getting web component token: %s", str(e))
            raise ValidationError(_("Could not connect to JustiFi. Please try again later."))

        if response.status_code != 200:
            _logger.error(
                "JustiFi: Failed to get web component token. Status: %s, Response: %s",
                response.status_code, response.text
            )
            raise ValidationError(_("JustiFi: Failed to initialize payment form."))

        data = response.json()
        token = data.get('access_token')

        if not token:
            _logger.error("JustiFi: No web component token in response: %s", data)
            raise ValidationError(_("JustiFi: Failed to initialize payment form."))

        _logger.info("JustiFi: Web component token obtained for checkout: %s", checkout_id)
        return token

    def _justifi_get_inline_form_values(self, amount, currency, partner_id, is_validation=False, **kwargs):
        """
        Get values needed for the JustiFi inline form.

        This method is called from the inline form template to get checkout
        and authentication values for the JustiFi web component.

        :param float amount: The payment amount
        :param recordset currency: The currency record
        :param int partner_id: The partner ID
        :param bool is_validation: Whether this is a validation transaction
        :return: JSON-encoded string of inline form values
        """
        import json
        from odoo.http import request
        self.ensure_one()

        if is_validation:
            # For validation (saving payment method), we don't need a checkout
            return json.dumps({})

        # Convert amount to cents
        amount_cents = int(amount * 100)

        # Get base URL
        base_url = self.get_base_url()

        # Create checkout session
        checkout = self._justifi_create_checkout(
            amount=amount_cents,
            currency=currency.name,
            description=f"Payment",
            origin_url=base_url,
        )

        checkout_id = checkout['id']

        # Find the pending transaction for this payment and store checkout_id
        # Look for draft/pending transaction matching this provider, amount, and currency
        tx = self.env['payment.transaction'].sudo().search([
            ('provider_id', '=', self.id),
            ('amount', '=', amount),
            ('currency_id', '=', currency.id),
            ('state', 'in', ['draft', 'pending']),
            ('provider_reference', '=', False),
        ], order='id desc', limit=1)

        if tx:
            tx.provider_reference = checkout_id
            _logger.info("JustiFi: Stored checkout_id %s in transaction %s", checkout_id, tx.reference)

        # Get web component token
        auth_token = self._justifi_get_web_component_token(checkout_id)

        values = {
            'checkout_id': checkout_id,
            'auth_token': auth_token,
            'account_id': self.justifi_account_id,
            'payment_method_group_id': self.justifi_payment_method_group_id or '',
            'api_url': '/payment/justifi/complete',
        }

        return json.dumps(values)

    def _justifi_get_checkout(self, checkout_id):
        """
        Get checkout details from JustiFi.

        :param checkout_id: The checkout ID to retrieve
        :return: Checkout data dict
        :raises ValidationError: If request fails
        """
        self.ensure_one()

        access_token = self._justifi_get_access_token()

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Sub-Account': self.justifi_account_id,
        }

        url = f'{CHECKOUTS_URL}/{checkout_id}'

        _logger.info("JustiFi: Getting checkout: %s", checkout_id)

        try:
            response = requests.get(url, headers=headers, timeout=30)
        except requests.exceptions.RequestException as e:
            _logger.error("JustiFi: Network error getting checkout: %s", str(e))
            raise ValidationError(_("Could not connect to JustiFi. Please try again later."))

        if response.status_code >= 400:
            _logger.error(
                "JustiFi: Failed to get checkout. Status: %s, Response: %s",
                response.status_code, response.text
            )
            raise ValidationError(_("JustiFi: Failed to verify payment status."))

        data = response.json()
        return data.get('data', data)
