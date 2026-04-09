import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEPOSIT_AMOUNT = 500.00


class PosOrder(models.Model):
    _inherit = 'pos.order'

    is_deposit = fields.Boolean('Is Deposit', default=False)
    deposit_state = fields.Selection([
        ('active', 'Active'),
        ('redeemed', 'Redeemed'),
    ], string='Deposit Status')
    deposit_redeemed_order_id = fields.Many2one(
        'pos.order', string='Redeemed On Order',
        help='The POS order where this deposit was applied.',
    )
    deposit_origin_order_id = fields.Many2one(
        'pos.order', string='Deposit Origin',
        help='The original deposit order (on the redemption order).',
    )
    deposit_reference = fields.Char(
        'Deposit Reference', compute='_compute_deposit_reference', store=True,
    )

    @api.depends('is_deposit', 'name')
    def _compute_deposit_reference(self):
        for order in self:
            if order.is_deposit and order.name:
                # Use the POS order name (e.g., "Order 00001-001-0001") to derive reference
                order.deposit_reference = f'DEP-{order.name}'
            else:
                order.deposit_reference = False

    @api.model
    def _order_fields(self, ui_order):
        fields_dict = super()._order_fields(ui_order)
        fields_dict['is_deposit'] = ui_order.get('is_deposit', False)
        if fields_dict['is_deposit']:
            fields_dict['deposit_state'] = 'active'
        # Handle deposit redemption
        deposit_origin_order_id = ui_order.get('deposit_origin_order_id', False)
        if deposit_origin_order_id:
            fields_dict['deposit_origin_order_id'] = deposit_origin_order_id
        return fields_dict

    @api.model
    def create(self, vals):
        order = super().create(vals)
        # If this order redeems a deposit, mark the original deposit as redeemed
        if order.deposit_origin_order_id:
            deposit_order = order.deposit_origin_order_id
            deposit_order.write({
                'deposit_state': 'redeemed',
                'deposit_redeemed_order_id': order.id,
            })
            _logger.info(
                'Deposit %s redeemed on order %s',
                deposit_order.deposit_reference, order.name,
            )
        return order

    def refund(self):
        """Block refunds on deposit orders."""
        for order in self:
            if order.is_deposit:
                raise UserError(_(
                    'Deposit %s is non-refundable and cannot be refunded.',
                    order.deposit_reference,
                ))
        return super().refund()

    @api.model
    def get_active_deposits(self, partner_id):
        """Return active deposits for a customer. Called from POS frontend via RPC."""
        deposits = self.search([
            ('partner_id', '=', partner_id),
            ('is_deposit', '=', True),
            ('deposit_state', '=', 'active'),
        ], order='date_order desc')

        return [{
            'id': dep.id,
            'deposit_reference': dep.deposit_reference,
            'date_order': dep.date_order.strftime('%Y-%m-%d %H:%M') if dep.date_order else '',
            'amount': DEPOSIT_AMOUNT,
            'name': dep.name,
            'partner_name': dep.partner_id.name,
        } for dep in deposits]
