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
