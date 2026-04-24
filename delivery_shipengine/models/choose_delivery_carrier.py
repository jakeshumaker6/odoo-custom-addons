# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ChooseDeliveryCarrier(models.TransientModel):
    _inherit = 'choose.delivery.carrier'

    # True only when display_price / delivery_price reflect a successful rate
    # fetch for the CURRENT total_weight. Flipped to False whenever the user
    # changes weight or carrier; flipped back to True after _get_delivery_rate
    # returns a non-error response.
    #
    # Consumed by the inherited form view to:
    #   - hide display_price + its label until a fresh rate is available
    #   - hide the Add button until a fresh rate is available
    #
    # Both gates matter: even if the client briefly flashes a stale price
    # during the act_window dialog reopen, the Add button is simultaneously
    # hidden, so the user physically cannot commit a stale rate to the SO.
    rate_is_current = fields.Boolean(default=False)

    @api.onchange('carrier_id', 'total_weight')
    def _onchange_carrier_id(self):
        res = super()._onchange_carrier_id()
        # Base method already zeros display_price + delivery_price for API
        # carriers in its else branch; we add the staleness flag so the view
        # has one clear signal to gate both the price and the Add button.
        if self.delivery_type not in ('fixed', 'base_on_rule'):
            self.rate_is_current = False
        else:
            # Fixed / base_on_rule carriers compute synchronously; their rate
            # is always current after onchange completes.
            self.rate_is_current = True
        return res

    def _get_delivery_rate(self):
        vals = super()._get_delivery_rate()
        if not vals.get('error_message'):
            self.rate_is_current = True
        return vals
