# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Shared fixtures for payment_justifi tests.

Webhook handlers are invoked directly as Python method calls against a
controller or transaction instance — we deliberately bypass HTTP routing
because we want to verify the pure business logic (state transitions,
reconciliation reversal, chatter messages) without booting a full HTTP stack.
"""

from odoo.tests.common import TransactionCase


class JustiFiWebhookTestCommon(TransactionCase):
    """Base for webhook tests. Creates a provider, invoice, and successful tx."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.provider = cls.env['payment.provider'].create({
            'name': 'JustiFi Test',
            'code': 'justifi',
            'state': 'test',
            'justifi_client_id': 'test_client',
            'justifi_client_secret': 'test_secret',
            'justifi_account_id': 'acc_test123',
            'justifi_payment_methods': 'both',
        })

        cls.payment_method = cls.env['payment.method'].search(
            [('code', '=', 'bank_sepa')], limit=1
        ) or cls.env['payment.method'].create({
            'name': 'JustiFi (test)',
            'code': 'bank_sepa',
            'provider_ids': [(4, cls.provider.id)],
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
        })

        cls.invoice = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': cls.partner.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Widget',
                'quantity': 1,
                'price_unit': 100.0,
            })],
        })
        cls.invoice.action_post()

        cls.tx = cls.env['payment.transaction'].create({
            'reference': 'JUSTIFI-TEST-001',
            'provider_id': cls.provider.id,
            'payment_method_id': cls.payment_method.id,
            'amount': 100.0,
            'currency_id': cls.invoice.currency_id.id,
            'partner_id': cls.partner.id,
            'provider_reference': 'py_test_payment_001',
            'invoice_ids': [(4, cls.invoice.id)],
        })

    def _make_dispute_payload(self, event_type='payment.disputed',
                               payment_id='py_test_payment_001',
                               dispute_id='dp_test_dispute_001',
                               status='needs_response',
                               reason_code=None,
                               reason_message=None,
                               amount=10000):
        """Build a mock JustiFi dispute webhook envelope."""
        data = {
            'id': dispute_id,
            'payment_id': payment_id,
            'status': status,
            'amount': amount,
        }
        if reason_code:
            data['reason_code'] = reason_code
        if reason_message:
            data['reason_message'] = reason_message
        return {
            'event_type': event_type,
            'data': data,
        }
