from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    partner_shipping_id = fields.Many2one(
        'res.partner',
        string='Delivery Address',
        compute='_compute_partner_shipping_id',
    )

    @api.depends('partner_id', 'shipping_date')
    def _compute_partner_shipping_id(self):
        for order in self:
            if order.shipping_date and order.partner_id:
                # Ship Later: use customer's delivery address for tax
                order.partner_shipping_id = order.partner_id.address_get(['delivery'])['delivery']
            elif order.config_id.warehouse_id and order.config_id.warehouse_id.partner_id:
                # Take Now: always use POS warehouse for tax
                order.partner_shipping_id = order.config_id.warehouse_id.partner_id.id
            else:
                order.partner_shipping_id = False

    def _get_avatax_ship_to_partner(self):
        """Override: Use warehouse for Take Now, customer for Ship Later."""
        if self.shipping_date and self.partner_id:
            return self.partner_id
        if self.config_id.warehouse_id and self.config_id.warehouse_id.partner_id:
            return self.config_id.warehouse_id.partner_id
        return self.partner_id or self.env['res.partner']

    def _get_avatax_address_from_partner(self, partner):
        """Override: Fall back to warehouse address if partner address is incomplete."""
        if partner and partner.zip and partner.state_id and partner.country_id:
            return super()._get_avatax_address_from_partner(partner)

        # Partner has incomplete address — fall back to warehouse
        warehouse_partner = self.config_id.warehouse_id.partner_id if self.config_id.warehouse_id else None
        if warehouse_partner and warehouse_partner.zip and warehouse_partner.state_id:
            _logger.info(
                'AvaTax: Partner %s has incomplete address, falling back to warehouse %s',
                partner.name if partner else 'None',
                warehouse_partner.name,
            )
            return super()._get_avatax_address_from_partner(warehouse_partner)

        # Last resort: raise the original error
        if not partner:
            raise ValidationError(_(
                'Avatax requires your current location or a customer to be set '
                'on the order with a proper zip, state and country.'
            ))
        return super()._get_avatax_address_from_partner(partner)

    def _get_line_data_for_external_taxes(self):
        """Override to return base_line dicts compatible with the Odoo 19 tax engine.

        The stock pos_avatax module returns a flat dict, but account_avatax
        expects each entry to have a 'base_line' key containing a dict built
        by account.tax._prepare_base_line_for_taxes_computation().
        """
        self.ensure_one()
        AccountTax = self.env['account.tax']
        res = []

        # Determine the shipping partner for line-level address resolution
        shipping_partner = self.partner_shipping_id or self.partner_id
        if not shipping_partner and self.config_id.warehouse_id:
            shipping_partner = self.config_id.warehouse_id.partner_id

        for line in self.lines:
            base_line = AccountTax._prepare_base_line_for_taxes_computation(
                line,
                price_unit=line.price_unit,
                quantity=line.qty,
                discount=line.discount,
                currency_id=line.currency_id,
                product_id=line.product_id,
                product_uom_id=line.product_uom_id,
                tax_ids=line.tax_ids,
                extra_tax_data=line.extra_tax_data or {},
            )
            res.append({
                'base_line': base_line,
                'description': line.full_product_name or line.product_id.display_name,
                'warehouse_id': self.config_id.warehouse_id if self.config_id.ship_later else False,
                'shipping_partner': shipping_partner,
            })

        if res:
            base_lines = [r['base_line'] for r in res]
            AccountTax._add_tax_details_in_base_lines(base_lines, self.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, self.company_id)

        return res
