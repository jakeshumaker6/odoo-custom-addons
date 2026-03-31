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
