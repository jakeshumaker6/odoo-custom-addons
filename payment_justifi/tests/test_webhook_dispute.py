# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""End-to-end tests for the JustiFi dispute webhook flow.

Covers:
- Dispute opens → invoice marked 'open', chatter message posted, activity
  scheduled for salesperson, but payment stays reconciled.
- Dispute lost (ACH return with R01) → invoice marked 'lost', payment
  reconciliation reversed, chatter message posted, customer email queued.
- Dispute won → invoice marked 'won', no accounting changes.
- Invoiceless transaction → logs warning, does not raise.
"""

from unittest.mock import patch

from odoo.tests import tagged

from .common import JustiFiWebhookTestCommon


@tagged('post_install', '-at_install', 'payment_justifi')
class TestDisputeOpen(JustiFiWebhookTestCommon):
    """A dispute.created event opens a dispute but does not reverse payment."""

    def test_payment_disputed_sets_invoice_to_open(self):
        payload = self._make_dispute_payload(
            event_type='payment.disputed',
            status='needs_response',
            reason_code='R01',
            reason_message='Insufficient funds',
        )
        self.tx._justifi_handle_dispute(payload['event_type'], payload['data'])

        self.invoice.invalidate_recordset()
        self.assertEqual(self.invoice.justifi_dispute_state, 'open')
        self.assertEqual(self.invoice.justifi_dispute_id, 'dp_test_dispute_001')
        self.assertIn('R01', self.invoice.justifi_dispute_reason)
        self.assertIn('Insufficient funds', self.invoice.justifi_dispute_reason)

    def test_dispute_open_posts_chatter_message(self):
        payload = self._make_dispute_payload(
            event_type='dispute.created',
            status='needs_response',
            reason_code='R01',
        )
        messages_before = len(self.invoice.message_ids)
        self.tx._justifi_handle_dispute(payload['event_type'], payload['data'])
        self.invoice.invalidate_recordset()
        self.assertGreater(len(self.invoice.message_ids), messages_before,
                           "Dispute handler must post a chatter message on the invoice")
        latest = self.invoice.message_ids[0]
        self.assertIn('ACH return', latest.body)

    def test_dispute_open_creates_activity_for_salesperson(self):
        payload = self._make_dispute_payload(
            event_type='dispute.created',
            status='needs_response',
        )
        activities_before = self.invoice.activity_ids
        self.tx._justifi_handle_dispute(payload['event_type'], payload['data'])
        self.invoice.invalidate_recordset()
        new_activities = self.invoice.activity_ids - activities_before
        self.assertTrue(new_activities,
                        "Dispute handler must schedule a follow-up activity")


@tagged('post_install', '-at_install', 'payment_justifi')
class TestDisputeLost(JustiFiWebhookTestCommon):
    """A dispute.lost event must reverse the payment and notify the customer."""

    def test_dispute_lost_sets_state_to_lost(self):
        payload = self._make_dispute_payload(
            event_type='dispute.lost',
            status='lost',
            reason_code='R01',
            reason_message='Insufficient funds',
        )
        with patch.object(
            type(self.tx), '_justifi_reverse_payment_on_dispute', return_value=None
        ):
            self.tx._justifi_handle_dispute(payload['event_type'], payload['data'])

        self.invoice.invalidate_recordset()
        self.assertEqual(self.invoice.justifi_dispute_state, 'lost')

    def test_dispute_lost_attempts_to_reverse_reconciliation(self):
        payload = self._make_dispute_payload(
            event_type='dispute.lost',
            status='lost',
            reason_code='R01',
        )
        with patch.object(
            type(self.tx), '_justifi_reverse_payment_on_dispute', return_value=None
        ) as mock_reverse:
            self.tx._justifi_handle_dispute(payload['event_type'], payload['data'])
        mock_reverse.assert_called_once()

    def test_dispute_lost_queues_customer_email(self):
        payload = self._make_dispute_payload(
            event_type='dispute.lost',
            status='lost',
            reason_code='R01',
        )
        with patch.object(
            type(self.tx), '_justifi_reverse_payment_on_dispute', return_value=None
        ), patch.object(
            type(self.tx), '_justifi_notify_customer_of_return', return_value=None
        ) as mock_notify:
            self.tx._justifi_handle_dispute(payload['event_type'], payload['data'])
        mock_notify.assert_called_once()

    def test_dispute_open_does_NOT_reverse_payment(self):
        """Open disputes leave the payment reconciliation intact."""
        payload = self._make_dispute_payload(
            event_type='dispute.created',
            status='needs_response',
        )
        with patch.object(
            type(self.tx), '_justifi_reverse_payment_on_dispute', return_value=None
        ) as mock_reverse, patch.object(
            type(self.tx), '_justifi_notify_customer_of_return', return_value=None
        ) as mock_notify:
            self.tx._justifi_handle_dispute(payload['event_type'], payload['data'])
        mock_reverse.assert_not_called()
        mock_notify.assert_not_called()


@tagged('post_install', '-at_install', 'payment_justifi')
class TestDisputeWon(JustiFiWebhookTestCommon):
    """A dispute.won event closes the dispute without accounting changes."""

    def test_dispute_won_sets_state_to_won(self):
        payload = self._make_dispute_payload(
            event_type='dispute.won',
            status='won',
        )
        self.tx._justifi_handle_dispute(payload['event_type'], payload['data'])
        self.invoice.invalidate_recordset()
        self.assertEqual(self.invoice.justifi_dispute_state, 'won')

    def test_dispute_won_does_NOT_reverse_or_notify(self):
        payload = self._make_dispute_payload(
            event_type='dispute.won',
            status='won',
        )
        with patch.object(
            type(self.tx), '_justifi_reverse_payment_on_dispute', return_value=None
        ) as mock_reverse, patch.object(
            type(self.tx), '_justifi_notify_customer_of_return', return_value=None
        ) as mock_notify:
            self.tx._justifi_handle_dispute(payload['event_type'], payload['data'])
        mock_reverse.assert_not_called()
        mock_notify.assert_not_called()


@tagged('post_install', '-at_install', 'payment_justifi')
class TestDisputeInvoiceless(JustiFiWebhookTestCommon):
    """Transaction-level edge case: dispute on a tx with no linked invoices."""

    def test_dispute_on_tx_without_invoice_does_not_raise(self):
        """A dispute against a transaction that has no invoice should log and
        not raise. Unreconciled transactions still exist (manual tokenize tests,
        standalone charges) — we must not blow up the webhook handler."""
        bare_tx = self.env['payment.transaction'].create({
            'reference': 'JUSTIFI-BARE-001',
            'provider_id': self.provider.id,
            'payment_method_id': self.payment_method.id,
            'amount': 50.0,
            'currency_id': self.invoice.currency_id.id,
            'partner_id': self.partner.id,
            'provider_reference': 'py_bare_payment',
        })
        payload = self._make_dispute_payload(
            event_type='dispute.created',
            status='needs_response',
            payment_id='py_bare_payment',
        )
        bare_tx._justifi_handle_dispute(payload['event_type'], payload['data'])


@tagged('post_install', '-at_install', 'payment_justifi')
class TestAchReturnDetection(JustiFiWebhookTestCommon):
    """Messages must distinguish ACH returns from credit-card chargebacks."""

    def test_ach_return_code_produces_ach_language(self):
        payload = self._make_dispute_payload(
            event_type='dispute.created',
            reason_code='R01',
            reason_message='Insufficient funds',
        )
        self.tx._justifi_handle_dispute(payload['event_type'], payload['data'])
        self.invoice.invalidate_recordset()
        latest = self.invoice.message_ids[0]
        self.assertIn('ACH return', latest.body,
                      "R01 should be labeled as an ACH return in chatter")

    def test_chargeback_reason_produces_dispute_language(self):
        payload = self._make_dispute_payload(
            event_type='dispute.created',
            reason_code='fraudulent',
            reason_message='Cardholder claims fraud',
        )
        self.tx._justifi_handle_dispute(payload['event_type'], payload['data'])
        self.invoice.invalidate_recordset()
        latest = self.invoice.message_ids[0]
        self.assertIn('Dispute/Chargeback', latest.body,
                      "Non-NACHA codes should be labeled as generic chargebacks")
