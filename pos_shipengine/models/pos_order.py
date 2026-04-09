import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    shipping_tier = fields.Selection([
        ('express', 'Express'),
        ('standard', 'Standard'),
        ('economy', 'Economy'),
        ('custom', 'Custom'),
    ], string='Shipping Tier')
    shipping_amount = fields.Float('Shipping Amount')
    shipping_carrier_name = fields.Char('Shipping Carrier')
    shipping_service_code = fields.Char('Shipping Service Code')
    shipping_rate_id = fields.Char('ShipEngine Rate ID')

    @api.model
    def _order_fields(self, ui_order):
        fields_dict = super()._order_fields(ui_order)
        fields_dict['shipping_tier'] = ui_order.get('shipping_tier', False)
        fields_dict['shipping_amount'] = ui_order.get('shipping_amount', 0.0)
        fields_dict['shipping_carrier_name'] = ui_order.get('shipping_carrier_name', '')
        fields_dict['shipping_service_code'] = ui_order.get('shipping_service_code', '')
        fields_dict['shipping_rate_id'] = ui_order.get('shipping_rate_id', '')
        return fields_dict


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    is_shipping_charge = fields.Boolean('Is Shipping Charge', default=False)

    @api.model
    def _order_line_fields(self, line, session_id=None):
        fields_dict = super()._order_line_fields(line, session_id=session_id)
        fields_dict[2]['is_shipping_charge'] = line[2].get('is_shipping_charge', False)
        return fields_dict
