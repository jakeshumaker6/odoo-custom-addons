# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, models
from odoo.exceptions import ValidationError

from ..const import STATUS_MAPPING

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    # === BUSINESS METHODS ===#

    def _get_specific_rendering_values(self, processing_values):
        """
        Return JustiFi-specific rendering values for the payment form.

        This method is called when rendering the payment form template.
        It creates a JustiFi checkout session and returns the values needed
        for the frontend to initialize the JustiFi modular checkout component.

        :param dict processing_values: The generic processing values
        :return: dict of JustiFi-specific rendering values
        """
        res = super()._get_specific_rendering_values(processing_values)

        if self.provider_code != 'justifi':
            return res

        provider = self.provider_id

        # Convert amount to cents (JustiFi expects integer cents)
        amount_cents = int(self.amount * 100)

        # Get the base URL for origin
        base_url = self.provider_id.get_base_url()

        # Create checkout session
        try:
            checkout = provider._justifi_create_checkout(
                amount=amount_cents,
                currency=self.currency_id.name,
                description=f"Payment for {self.reference}",
                origin_url=base_url,
            )
        except ValidationError as e:
            _logger.error("JustiFi: Failed to create checkout for transaction %s: %s", self.reference, str(e))
            raise

        checkout_id = checkout['id']

        # Store checkout_id in provider_reference for later lookup
        self.provider_reference = checkout_id

        # Get web component token
        try:
            auth_token = provider._justifi_get_web_component_token(checkout_id)
        except ValidationError as e:
            _logger.error("JustiFi: Failed to get web component token for %s: %s", checkout_id, str(e))
            raise

        _logger.info(
            "JustiFi: Rendering values for transaction %s: checkout_id=%s",
            self.reference, checkout_id
        )

        res.update({
            'checkout_id': checkout_id,
            'auth_token': auth_token,
            'account_id': provider.justifi_account_id,
            'payment_method_group_id': provider.justifi_payment_method_group_id or '',
            'api_url': f"/payment/justifi/complete",
        })

        return res

    def _get_specific_processing_values(self, processing_values):
        """
        Return JustiFi-specific processing values.

        :param dict processing_values: The generic processing values
        :return: dict of JustiFi-specific values
        """
        res = super()._get_specific_processing_values(processing_values)

        if self.provider_code != 'justifi':
            return res

        # Add any JustiFi-specific values needed during processing
        res.update({
            'justifi_checkout_id': self.provider_reference,
        })

        return res

    def _justifi_process_payment_data(self, payment_data):
        """
        Process payment data received from JustiFi (via webhook or return).

        :param dict payment_data: Payment data from JustiFi
        :return: None
        """
        self.ensure_one()

        checkout_id = payment_data.get('checkout_id') or payment_data.get('id')
        status = payment_data.get('status', '')
        payment_id = payment_data.get('successful_payment_id', '')

        _logger.info(
            "JustiFi: Processing payment data for %s: status=%s, payment_id=%s",
            self.reference, status, payment_id
        )

        # Map JustiFi status to Odoo transaction state
        odoo_state = STATUS_MAPPING.get(status, 'pending')

        # Store the payment ID as provider reference if available
        if payment_id:
            self.provider_reference = payment_id
        elif checkout_id and not self.provider_reference:
            self.provider_reference = checkout_id

        # Update transaction state
        if odoo_state == 'done':
            self._set_done()
            # Trigger immediate post-processing to reconcile invoice
            # This creates the payment and marks the invoice as paid
            try:
                self._post_process()
                _logger.info("JustiFi: Post-processing completed for transaction %s", self.reference)
            except Exception as e:
                _logger.exception("JustiFi: Post-processing failed for transaction %s: %s", self.reference, str(e))
        elif odoo_state == 'pending':
            self._set_pending()
        elif odoo_state == 'error':
            error_msg = payment_data.get('error', {}).get('message', 'Payment failed')
            self._set_error(f"JustiFi: {error_msg}")
        elif odoo_state == 'cancel':
            self._set_canceled()

    @staticmethod
    def _justifi_get_tx_from_notification_data(provider, notification_data):
        """
        Find the transaction based on JustiFi notification data.

        :param provider: The payment provider
        :param notification_data: The notification data from JustiFi
        :return: The matching transaction recordset
        :raises ValidationError: If transaction not found
        """
        checkout_id = notification_data.get('checkout_id') or notification_data.get('data', {}).get('id')
        payment_id = notification_data.get('successful_payment_id') or notification_data.get('data', {}).get('successful_payment_id')

        if not checkout_id and not payment_id:
            raise ValidationError("JustiFi: Missing checkout_id or payment_id in notification data")

        # Try to find by checkout_id first (stored in provider_reference)
        tx = provider.env['payment.transaction']

        if checkout_id:
            tx = tx.search([
                ('provider_reference', '=', checkout_id),
                ('provider_id', '=', provider.id),
            ], limit=1)

        # If not found, try by payment_id
        if not tx and payment_id:
            tx = tx.search([
                ('provider_reference', '=', payment_id),
                ('provider_id', '=', provider.id),
            ], limit=1)

        if not tx:
            _logger.error(
                "JustiFi: Transaction not found for checkout_id=%s, payment_id=%s",
                checkout_id, payment_id
            )
            raise ValidationError("JustiFi: Transaction not found")

        return tx
