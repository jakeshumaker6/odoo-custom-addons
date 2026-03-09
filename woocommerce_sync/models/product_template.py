# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    wc_id = fields.Integer(
        string="WooCommerce ID",
        index=True,
        copy=False,
        help="The product ID in WooCommerce.",
    )
    wc_backend_id = fields.Many2one(
        'wc.backend',
        string="WooCommerce Store",
        copy=False,
    )
    wc_permalink = fields.Char(
        string="WooCommerce URL",
        copy=False,
    )
    wc_product_type = fields.Selection(
        selection=[
            ('simple', 'Simple'),
            ('variable', 'Variable'),
            ('grouped', 'Grouped'),
            ('external', 'External'),
        ],
        string="WC Product Type",
        copy=False,
    )
    wc_sync_needed = fields.Boolean(
        string="Needs WC Sync",
        default=False,
        copy=False,
        help="Set to True when changes need to be pushed to WooCommerce.",
    )
    wc_last_synced = fields.Datetime(
        string="Last WC Sync",
        copy=False,
    )
