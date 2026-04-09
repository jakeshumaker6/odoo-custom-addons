import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PosShipEngineController(http.Controller):

    @http.route('/pos_shipengine/get_rates', type='json', auth='user')
    def get_rates(self, partner_id, config_id, order_line_data=None):
        """Fetch ShipEngine shipping rates for a POS Ship Later order.

        :param partner_id: ID of the customer (ship-to address)
        :param config_id: ID of the POS config
        :param order_line_data: list of dicts with product_id and qty
        :returns: dict with tiers list and raw_rate_count
        """
        try:
            config = request.env['pos.config'].sudo().browse(config_id)
            carrier = config.shipengine_carrier_id

            if not carrier:
                return {'error': 'No ShipEngine carrier configured on this POS.'}

            partner = request.env['res.partner'].sudo().browse(partner_id)
            if not partner.exists():
                return {'error': 'Customer not found.'}

            if not partner.street or not partner.city or not partner.zip:
                return {'error': 'Customer address is incomplete. Street, city, and zip are required.'}

            # Build pseudo order lines for weight calculation
            order_lines = None
            if order_line_data:
                # Create temporary recordset-like objects for weight calc
                ProductProduct = request.env['product.product'].sudo()
                lines = []
                for line_data in order_line_data:
                    product = ProductProduct.browse(line_data.get('product_id'))
                    if product.exists():
                        lines.append(type('PseudoLine', (), {
                            'product_id': product,
                            'qty': line_data.get('qty', 1),
                        })())
                order_lines = lines or None

            result = carrier.shipengine_get_all_rates(partner, order_lines=order_lines)
            return result

        except Exception as exc:
            _logger.exception('POS ShipEngine rate fetch error: %s', exc)
            return {'error': str(exc)}
