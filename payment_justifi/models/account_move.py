# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


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
