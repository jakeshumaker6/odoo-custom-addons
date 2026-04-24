# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    justifi_payment_methods = fields.Selection(
        selection=[
            ('card', 'Card Only'),
            ('ach', 'ACH/Bank Account Only'),
            ('both', 'Card and ACH'),
        ],
        string="Payment Methods",
        default='both',
        help="Select which payment methods to offer the customer for this invoice. "
             "This overrides the default setting on the JustiFi payment provider.",
    )

    justifi_dispute_state = fields.Selection(
        selection=[
            ('none', 'No Dispute'),
            ('open', 'Disputed'),
            ('won', 'Dispute Won'),
            ('lost', 'Dispute Lost / Payment Reversed'),
        ],
        string="JustiFi Dispute Status",
        default='none',
        readonly=True,
        copy=False,
        tracking=True,
        help="Set automatically when a JustiFi dispute webhook fires against a payment "
             "linked to this invoice. 'Open' means the dispute is in progress. 'Lost' "
             "means the payment was reversed — the invoice has been moved back to unpaid "
             "and accounting/salesperson have been notified.",
    )
    justifi_dispute_reason = fields.Char(
        string="Dispute Reason",
        readonly=True,
        copy=False,
        help="Reason code and message from JustiFi. For ACH returns this is the NACHA "
             "code (e.g. R01 = Insufficient funds).",
    )
    justifi_dispute_id = fields.Char(
        string="JustiFi Dispute ID",
        readonly=True,
        copy=False,
        help="The JustiFi dispute record ID (dp_xxx) for audit trail.",
    )

    def action_pay_on_terminal(self):
        """Open the terminal payment wizard for this invoice."""
        self.ensure_one()
        return {
            'name': _("Pay on Terminal"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move.terminal.payment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_invoice_id': self.id,
                'default_amount': self.amount_residual,
                'default_currency_id': self.currency_id.id,
            },
        }
