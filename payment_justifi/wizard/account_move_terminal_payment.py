# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AccountMoveTerminalPayment(models.TransientModel):
    _name = 'account.move.terminal.payment'
    _description = 'Pay Invoice on Terminal'

    invoice_id = fields.Many2one('account.move', string='Invoice', required=True, readonly=True)
    amount = fields.Monetary(string='Amount', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)

    terminal_id = fields.Selection(
        selection='_get_terminal_selection',
        string='Terminal',
        required=True,
    )

    state = fields.Selection([
        ('draft', 'Select Terminal'),
        ('waiting', 'Waiting for Payment'),
        ('done', 'Payment Completed'),
        ('error', 'Error'),
    ], default='draft', string='Status')

    checkout_id = fields.Char(string='Checkout ID')
    selected_terminal_id = fields.Char(string='Selected Terminal ID')
    terminal_action_id = fields.Char(string='Terminal Action ID')
    error_message = fields.Text(string='Error Message')
    payment_id = fields.Char(string='Payment ID')

    @api.model
    def _get_terminal_selection(self):
        """Build selection list from configured JustiFi terminals."""
        if 'pos.payment.method' not in self.env:
            return []
        terminals = self.env['pos.payment.method'].sudo().search([
            ('use_payment_terminal', '=', 'justifi'),
            ('justifi_terminal_id', '!=', False),
        ])
        return [(t.justifi_terminal_id, t.display_name) for t in terminals]

    def _get_provider(self):
        """Find the active JustiFi payment provider."""
        provider = self.env['payment.provider'].sudo().search([
            ('code', '=', 'justifi'),
            ('state', '!=', 'disabled'),
        ], limit=1)
        if not provider:
            raise ValidationError(_("No active JustiFi provider found."))
        return provider

    def action_send_to_terminal(self):
        """Create checkout and send to the selected terminal."""
        self.ensure_one()

        try:
            provider = self._get_provider()
            amount_cents = int(self.amount * 100)
            base_url = provider.get_base_url()
            invoice = self.invoice_id

            # Create checkout
            checkout = provider._justifi_create_checkout(
                amount=amount_cents,
                currency=self.currency_id.name,
                description=f"Invoice {invoice.name}",
                origin_url=base_url,
            )
            checkout_id = checkout['id']

            # Send to terminal
            terminal_response = provider._justifi_send_to_terminal(
                terminal_id=self.terminal_id,
                checkout_id=checkout_id,
            )
            terminal_action_id = terminal_response.get('id', '')

            _logger.info(
                "JustiFi Terminal: Sent invoice %s to terminal %s (checkout=%s)",
                invoice.name, self.terminal_id, checkout_id,
            )

            self.write({
                'state': 'waiting',
                'checkout_id': checkout_id,
                'terminal_action_id': terminal_action_id,
                'selected_terminal_id': self.terminal_id,
            })

        except (ValidationError, Exception) as e:
            _logger.exception("JustiFi Terminal: Error sending to terminal: %s", str(e))
            self.write({
                'state': 'error',
                'error_message': str(e),
            })

        return self._reopen_wizard()

    def action_check_status(self):
        """Check terminal payment status (button handler)."""
        self.ensure_one()
        self._check_and_update_status()
        return self._reopen_wizard()

    def _check_and_update_status(self):
        """Poll checkout status and update wizard state. Returns status dict."""
        self.ensure_one()

        try:
            provider = self._get_provider()
            checkout = provider._justifi_get_checkout(self.checkout_id)
        except (ValidationError, Exception) as e:
            _logger.warning("JustiFi Terminal: Status check error: %s", str(e))
            return {'status': 'error', 'message': str(e)}

        status = checkout.get('status', '')
        payment_id = checkout.get('successful_payment_id', '')

        _logger.info("JustiFi Terminal: Checkout %s status=%s", self.checkout_id, status)

        result = {
            'status': status,
            'payment_id': payment_id,
            'is_paid': status in ('completed', 'succeeded'),
            'is_pending': status in ('pending', 'created'),
            'is_failed': status in ('failed', 'canceled', 'attempted'),
        }

        if result['is_paid']:
            self._record_payment(provider, payment_id)
            self.write({
                'state': 'done',
                'payment_id': payment_id,
            })
        elif result['is_failed']:
            self.write({
                'state': 'error',
                'error_message': _("Terminal payment %s.", status),
            })

        return result

    def action_cancel_terminal(self):
        """Cancel the terminal session."""
        self.ensure_one()

        try:
            provider = self._get_provider()
            if self.checkout_id and self.selected_terminal_id:
                provider._justifi_cancel_terminal_action(
                    terminal_id=self.selected_terminal_id,
                    checkout_id=self.checkout_id,
                )
                _logger.info("JustiFi Terminal: Cancelled checkout %s", self.checkout_id)
        except Exception as e:
            _logger.warning("JustiFi Terminal: Cancel error: %s", str(e))

        self.write({
            'state': 'draft',
            'checkout_id': False,
            'terminal_action_id': False,
            'selected_terminal_id': False,
        })
        return self._reopen_wizard()

    def action_retry(self):
        """Reset wizard to draft state for retry."""
        self.write({
            'state': 'draft',
            'checkout_id': False,
            'terminal_action_id': False,
            'selected_terminal_id': False,
            'error_message': False,
        })
        return self._reopen_wizard()

    def _record_payment(self, provider, payment_id):
        """Create payment.transaction and trigger post-processing to reconcile invoice."""
        invoice = self.invoice_id

        # Find payment method linked to JustiFi provider
        payment_method = self.env['payment.method'].sudo().search([
            ('provider_ids', 'in', [provider.id]),
        ], limit=1)
        if not payment_method:
            payment_method = self.env['payment.method'].sudo().search([
                ('code', '=', 'bank_sepa'),
            ], limit=1)

        if not payment_method:
            raise ValidationError(_("No payment method found for JustiFi."))

        reference = self.env['payment.transaction'].sudo()._compute_reference(
            'justifi', prefix='JUSTIFI-TERM',
        )

        tx = self.env['payment.transaction'].sudo().create({
            'provider_id': provider.id,
            'payment_method_id': payment_method.id,
            'reference': reference,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'partner_id': invoice.partner_id.id,
            'provider_reference': payment_id or self.checkout_id,
            'operation': 'online_direct',
            'invoice_ids': [(6, 0, [invoice.id])],
        })

        tx._set_done()
        tx._post_process()

        _logger.info(
            "JustiFi Terminal: Payment recorded for invoice %s (tx=%s, payment=%s)",
            invoice.name, tx.reference, payment_id,
        )

    def _reopen_wizard(self):
        """Return action to reopen this wizard with updated state."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
