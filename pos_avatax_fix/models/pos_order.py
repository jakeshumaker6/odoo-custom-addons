from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    partner_shipping_id = fields.Many2one(
        'res.partner',
        string='Delivery Address',
        compute='_compute_partner_shipping_id',
    )

    @api.depends('partner_id')
    def _compute_partner_shipping_id(self):
        for order in self:
            if order.partner_id:
                order.partner_shipping_id = order.partner_id.address_get(['delivery'])['delivery']
            else:
                order.partner_shipping_id = False

    def _get_line_data_for_external_taxes(self):
        """Override to return base_line dicts compatible with the Odoo 19 tax engine.

        The stock pos_avatax module returns a flat dict, but account_avatax
        expects each entry to have a 'base_line' key containing a dict built
        by account.tax._prepare_base_line_for_taxes_computation().
        """
        self.ensure_one()
        AccountTax = self.env['account.tax']
        res = []

        for line in self.lines:
            base_line = AccountTax._prepare_base_line_for_taxes_computation(
                line,
                price_unit=line.price_unit,
                quantity=line.qty,
                discount=line.discount,
                currency_id=line.currency_id,
                product_id=line.product_id,
                product_uom_id=line.product_uom_id,
                tax_ids=line.tax_ids,
                extra_tax_data=line.extra_tax_data or {},
            )
            res.append({
                'base_line': base_line,
                'description': line.full_product_name or line.product_id.display_name,
                'warehouse_id': self.config_id.warehouse_id if self.config_id.ship_later else False,
            })

        if res:
            base_lines = [r['base_line'] for r in res]
            AccountTax._add_tax_details_in_base_lines(base_lines, self.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, self.company_id)

        return res
