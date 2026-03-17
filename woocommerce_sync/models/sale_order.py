# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    wc_id = fields.Integer(
        string="WooCommerce Order ID",
        index=True,
        copy=False,
    )
    wc_backend_id = fields.Many2one(
        'wc.backend',
        string="WooCommerce Store",
        copy=False,
    )
    wc_order_status = fields.Char(
        string="WC Order Status",
        copy=False,
    )
    wc_order_key = fields.Char(
        string="WC Order Key",
        copy=False,
    )
    wc_payment_method = fields.Char(
        string="WC Payment Method",
        copy=False,
    )
    wc_date_created = fields.Datetime(
        string="WC Order Date",
        copy=False,
    )
    wc_order_note = fields.Text(
        string="WC Customer Note",
        copy=False,
    )
    wc_status_sync_needed = fields.Boolean(
        string="Needs WC Status Sync",
        default=False,
        copy=False,
    )

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals and not self.env.context.get('_wc_importing'):
            for order in self.filtered(lambda o: o.wc_id and o.wc_backend_id):
                order.with_context(_wc_importing=True).wc_status_sync_needed = True
        return res
