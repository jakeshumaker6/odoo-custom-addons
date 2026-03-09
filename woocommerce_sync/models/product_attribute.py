# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    wc_id = fields.Integer(
        string="WooCommerce Attribute ID",
        index=True,
        copy=False,
    )
    wc_backend_id = fields.Many2one(
        'wc.backend',
        string="WooCommerce Store",
        copy=False,
    )


class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    wc_id = fields.Integer(
        string="WooCommerce Term ID",
        index=True,
        copy=False,
    )
