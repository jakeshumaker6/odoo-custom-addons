# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    wc_id = fields.Integer(
        string="WooCommerce Category ID",
        index=True,
        copy=False,
    )
    wc_backend_id = fields.Many2one(
        'wc.backend',
        string="WooCommerce Store",
        copy=False,
    )
