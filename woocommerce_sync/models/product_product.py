# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


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
