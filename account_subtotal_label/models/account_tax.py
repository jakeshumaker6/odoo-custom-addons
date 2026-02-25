# -*- coding: utf-8 -*-
from odoo import models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    def _get_tax_totals_summary(self, base_lines, currency, company, cash_rounding=None):
        """Override to change 'Untaxed Amount' label to 'Subtotal'."""
        result = super()._get_tax_totals_summary(base_lines, currency, company, cash_rounding)

        # Replace "Untaxed Amount" with "Subtotal" in subtotals
        if result and 'subtotals' in result:
            for subtotal in result['subtotals']:
                if subtotal.get('name') == 'Untaxed Amount':
                    subtotal['name'] = 'Subtotal'

        return result
