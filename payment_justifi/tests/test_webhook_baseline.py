# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Regression safety net: existing webhook behavior must not regress."""

from odoo.tests import tagged

from .common import JustiFiWebhookTestCommon


@tagged('post_install', '-at_install', 'payment_justifi')
class TestWebhookBaseline(JustiFiWebhookTestCommon):
    """Verify that pre-existing webhook events still route correctly after
    the dispute router was added."""

    def test_dispute_events_are_routed(self):
        """All dispute event names must be recognized by the router."""
        from odoo.addons.payment_justifi.const import DISPUTE_EVENT_TYPES
        expected = {
            'payment.disputed',
            'dispute.created',
            'dispute.updated',
            'dispute.won',
            'dispute.lost',
        }
        self.assertEqual(set(DISPUTE_EVENT_TYPES), expected,
                         "Dispute event catalog drifted — controller must also update")

    def test_status_mapping_unchanged(self):
        """The original JustiFi→Odoo status mapping must remain stable."""
        from odoo.addons.payment_justifi.const import STATUS_MAPPING
        self.assertEqual(STATUS_MAPPING.get('succeeded'), 'done')
        self.assertEqual(STATUS_MAPPING.get('failed'), 'error')
        self.assertEqual(STATUS_MAPPING.get('pending'), 'pending')
        self.assertEqual(STATUS_MAPPING.get('canceled'), 'cancel')

    def test_dispute_lost_statuses_are_terminal_only(self):
        """Open-dispute statuses must NOT be in the lost set (would cause
        premature payment reversal on legitimate in-progress disputes)."""
        from odoo.addons.payment_justifi.const import (
            DISPUTE_LOST_STATUSES, DISPUTE_OPEN_STATUSES,
        )
        for open_status in DISPUTE_OPEN_STATUSES:
            self.assertNotIn(open_status, DISPUTE_LOST_STATUSES,
                             f"{open_status} is open, not lost — don't reverse payment on it")

    def test_new_dispute_fields_exist_on_invoice(self):
        """The three new fields on account.move must be installed."""
        self.assertIn('justifi_dispute_state', self.invoice._fields)
        self.assertIn('justifi_dispute_reason', self.invoice._fields)
        self.assertIn('justifi_dispute_id', self.invoice._fields)
        self.assertEqual(self.invoice.justifi_dispute_state, 'none',
                         "Default dispute state must be 'none' so existing invoices are unaffected")
