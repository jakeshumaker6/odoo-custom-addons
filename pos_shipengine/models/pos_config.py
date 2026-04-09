from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    shipengine_carrier_id = fields.Many2one(
        'delivery.carrier',
        string='ShipEngine Carrier',
        domain="[('delivery_type', '=', 'shipengine')]",
        help='Select the ShipEngine carrier for shipping rate quotes in POS.',
    )
