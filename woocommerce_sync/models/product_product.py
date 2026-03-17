# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

from ..const import VARIANT_SYNC_TRIGGER_FIELDS


class ProductProduct(models.Model):
    _inherit = 'product.product'

    wc_variant_id = fields.Integer(
        string="WooCommerce Variation ID",
        index=True,
        copy=False,
        help="The variation ID in WooCommerce.",
    )
    wc_variant_sync_needed = fields.Boolean(
        string="Variant Needs WC Sync",
        default=False,
        copy=False,
    )
    wc_price = fields.Float(
        string="WC Price",
        copy=False,
        help="Price imported from WooCommerce for this specific variant.",
    )

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('_wc_importing') and VARIANT_SYNC_TRIGGER_FIELDS & set(vals.keys()):
            for rec in self.filtered(lambda r: r.wc_variant_id and r.product_tmpl_id.wc_backend_id):
                rec.with_context(_wc_importing=True).wc_variant_sync_needed = True
        return res
