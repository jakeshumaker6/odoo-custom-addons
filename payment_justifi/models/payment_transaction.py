# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, models
from odoo.exceptions import ValidationError

from ..const import (
    STATUS_MAPPING,
    DISPUTE_LOST_STATUSES,
    DISPUTE_WON_STATUSES,
    ACH_RETURN_REASON_CODES,
)

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

        # Determine payment methods - use invoice setting if available, else provider default
        payment_methods = provider.justifi_payment_methods or 'both'
        if self.invoice_ids:
            # Use the first invoice's payment method setting if set
            invoice = self.invoice_ids[0]
            if invoice.justifi_payment_methods:
                payment_methods = invoice.justifi_payment_methods

        res.update({
            'checkout_id': checkout_id,
            'auth_token': auth_token,
            'account_id': provider.justifi_account_id,
            'payment_method_group_id': provider.justifi_payment_method_group_id or '',
            'api_url': f"/payment/justifi/complete",
            'payment_methods': payment_methods,
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

    def _justifi_handle_dispute(self, event_type, event_data):
        """
        Handle a JustiFi dispute webhook against this transaction.

        Dispute lifecycle:
        - ``payment.disputed`` / ``dispute.created`` — dispute opened; mark
          invoice as disputed, notify salesperson + accounting, but leave
          payment/reconciliation intact until outcome is known.
        - ``dispute.lost`` (or terminal status in DISPUTE_LOST_STATUSES) —
          money is gone. Reverse the payment reconciliation so the invoice
          moves back to "Not Paid", notify, and email the customer.
        - ``dispute.won`` — dispute resolved in our favor. Mark resolved,
          notify internally. No accounting changes (payment stays posted).

        :param str event_type: The JustiFi event name (e.g. ``payment.disputed``)
        :param dict event_data: The dispute object from the webhook payload
        """
        self.ensure_one()

        dispute_id = event_data.get('id') or event_data.get('dispute_id') or ''
        status = (event_data.get('status') or '').lower()
        reason_code = event_data.get('reason_code') or event_data.get('reason') or ''
        reason_msg = event_data.get('reason_message') or event_data.get('description') or ''
        amount_cents = event_data.get('amount') or 0

        is_ach_return = reason_code in ACH_RETURN_REASON_CODES
        dispute_type = _("ACH return") if is_ach_return else _("Dispute/Chargeback")

        _logger.info(
            "JustiFi: Dispute handler for tx=%s event=%s dispute=%s status=%s reason=%s",
            self.reference, event_type, dispute_id, status, reason_code,
        )

        invoices = self.invoice_ids
        if not invoices:
            _logger.warning(
                "JustiFi: Dispute %s on tx %s has no linked invoices; logging only",
                dispute_id, self.reference,
            )

        is_terminal_lost = (
            event_type == 'dispute.lost'
            or status in DISPUTE_LOST_STATUSES
        )
        is_terminal_won = (
            event_type == 'dispute.won'
            or status in DISPUTE_WON_STATUSES
        )

        if is_terminal_lost:
            invoice_state = 'lost'
        elif is_terminal_won:
            invoice_state = 'won'
        else:
            invoice_state = 'open'

        # 1. Update invoice dispute fields + post chatter message
        for invoice in invoices:
            invoice.sudo().write({
                'justifi_dispute_state': invoice_state,
                'justifi_dispute_reason': f"{reason_code}: {reason_msg}" if reason_code else reason_msg,
                'justifi_dispute_id': dispute_id,
            })
            body = self._justifi_format_dispute_chatter(
                dispute_type, event_type, status, reason_code, reason_msg,
                amount_cents, dispute_id, is_terminal_lost, is_terminal_won,
            )
            invoice.message_post(
                body=body,
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
            )

        # 2. If lost: reverse the payment reconciliation so invoice reopens as unpaid
        if is_terminal_lost:
            self._justifi_reverse_payment_on_dispute(dispute_id, reason_code, reason_msg)

        # 3. Create Odoo activities for follow-up (salesperson + accounting)
        self._justifi_create_dispute_activity(
            invoices, dispute_type, reason_code, reason_msg,
            is_terminal_lost, is_terminal_won,
        )

        # 4. On lost: email the customer (only once — when outcome is terminal)
        if is_terminal_lost and invoices:
            self._justifi_notify_customer_of_return(invoices, reason_code, is_ach_return)

    def _justifi_format_dispute_chatter(self, dispute_type, event_type, status,
                                         reason_code, reason_msg, amount_cents,
                                         dispute_id, is_lost, is_won):
        """Build the HTML body for the invoice chatter message."""
        amount_display = f"${amount_cents / 100:.2f}" if amount_cents else _("unknown amount")

        if is_lost:
            headline = _("⚠ Payment reversed — %s lost") % dispute_type
            outcome = _(
                "The payment has been reversed by JustiFi. This invoice has been "
                "moved back to <b>Not Paid</b> and accounting has been notified."
            )
        elif is_won:
            headline = _("✓ %s resolved in our favor") % dispute_type
            outcome = _("No action required. The payment stays posted.")
        else:
            headline = _("⚠ %s opened") % dispute_type
            outcome = _(
                "The payment is under review. The invoice remains marked as Paid "
                "until the dispute resolves. No action is required yet — "
                "accounting has been notified."
            )

        reason_line = ""
        if reason_code:
            reason_line = _("<li><b>Reason:</b> %s %s</li>") % (
                reason_code, f"— {reason_msg}" if reason_msg else ""
            )
        elif reason_msg:
            reason_line = _("<li><b>Reason:</b> %s</li>") % reason_msg

        return (
            f"<p><b>{headline}</b></p>"
            f"<ul>"
            f"<li><b>Amount:</b> {amount_display}</li>"
            f"<li><b>Event:</b> <code>{event_type}</code></li>"
            f"<li><b>Status:</b> {status or _('unknown')}</li>"
            f"{reason_line}"
            f"<li><b>Dispute ID:</b> <code>{dispute_id or _('n/a')}</code></li>"
            f"<li><b>Transaction:</b> {self.reference}</li>"
            f"</ul>"
            f"<p>{outcome}</p>"
        )

    def _justifi_reverse_payment_on_dispute(self, dispute_id, reason_code, reason_msg):
        """
        Reverse the reconciliation between this transaction's payment and its
        invoice(s), so the invoice returns to ``payment_state='not_paid'``.

        We do NOT cancel or void the account.payment record — it stays posted
        for audit — we just break the reconciliation. This matches how Odoo
        handles Stripe chargebacks natively.
        """
        self.ensure_one()

        payments = self.payment_id
        if not payments:
            _logger.warning(
                "JustiFi: Dispute %s — transaction %s has no linked account.payment; "
                "cannot reverse reconciliation",
                dispute_id, self.reference,
            )
            return

        for payment in payments:
            reconciled_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id.reconcile or l.account_id.account_type in ('asset_receivable', 'liability_payable')
            )
            if reconciled_lines:
                try:
                    reconciled_lines.remove_move_reconcile()
                    _logger.info(
                        "JustiFi: Dispute %s — reversed reconciliation on payment %s",
                        dispute_id, payment.name,
                    )
                except Exception as e:
                    _logger.exception(
                        "JustiFi: Failed to reverse reconciliation for payment %s: %s",
                        payment.name, str(e),
                    )

        if self.state == 'done':
            self._set_error(_(
                "JustiFi dispute lost — payment reversed. Dispute ID: %s. Reason: %s %s"
            ) % (dispute_id, reason_code, reason_msg))

    def _justifi_create_dispute_activity(self, invoices, dispute_type, reason_code,
                                           reason_msg, is_lost, is_won):
        """Create a follow-up activity on each disputed invoice."""
        if is_won:
            return

        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            return

        if is_lost:
            summary = _("%s lost — payment reversed, follow up with customer") % dispute_type
        else:
            summary = _("%s opened — monitor and respond if needed") % dispute_type

        note_parts = [summary]
        if reason_code:
            note_parts.append(_("Reason code: %s") % reason_code)
        if reason_msg:
            note_parts.append(reason_msg)
        note = "<br/>".join(note_parts)

        for invoice in invoices:
            responsible = invoice.invoice_user_id or invoice.user_id or invoice.create_uid
            if not responsible:
                continue
            invoice.sudo().activity_schedule(
                activity_type_id=activity_type.id,
                summary=summary,
                note=note,
                user_id=responsible.id,
            )

    def _justifi_notify_customer_of_return(self, invoices, reason_code, is_ach_return):
        """Email the customer that their payment failed and invoice is owed again."""
        template = self.env.ref(
            'payment_justifi.mail_template_dispute_lost',
            raise_if_not_found=False,
        )
        if not template:
            _logger.warning(
                "JustiFi: Dispute lost template not found; skipping customer email"
            )
            return

        for invoice in invoices:
            if not invoice.partner_id.email:
                _logger.info(
                    "JustiFi: Invoice %s partner has no email; skipping notification",
                    invoice.name,
                )
                continue
            try:
                template.sudo().with_context(
                    is_ach_return=is_ach_return,
                    reason_code=reason_code,
                ).send_mail(invoice.id, force_send=False)
                _logger.info(
                    "JustiFi: Queued dispute-lost email for invoice %s to %s",
                    invoice.name, invoice.partner_id.email,
                )
            except Exception as e:
                _logger.exception(
                    "JustiFi: Failed to send dispute-lost email for %s: %s",
                    invoice.name, str(e),
                )

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
