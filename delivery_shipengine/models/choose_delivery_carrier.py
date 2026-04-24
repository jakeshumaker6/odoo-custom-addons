# -*- coding: utf-8 -*-
import logging

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ChooseDeliveryCarrier(models.TransientModel):
    _inherit = 'choose.delivery.carrier'

    def button_confirm(self):
        """Re-fetch the rate for the CURRENT total_weight before committing
        the delivery line to the sale order. Guards against committing a
        stale rate that can briefly linger on the wizard during the
        act_window dialog reopen after Get rate.

        User-visible scenario this prevents:
          1. User sets weight=10 lb, clicks Get rate -> sees $6.20
          2. User changes weight to 20 lb (price hides via 1.4.0 fix)
          3. User clicks Get rate; during the ~3s API roundtrip the old
             $6.20 briefly reappears in the refreshed dialog
          4. User clicks Add during that flash
          -> without this guard, $6.20 gets written to the SO despite
             the user having typed 20 lb

        By re-running _get_delivery_rate here we guarantee display_price
        and delivery_price reflect the total_weight value that is live on
        the wizard at the moment Add is clicked. One extra API call on
        confirm; no UI changes; no new fields.

        Only fires for API-based carriers (fixed / base_on_rule compute
        synchronously on onchange and can never be stale).
        """
        if self.delivery_type not in ('fixed', 'base_on_rule'):
            vals = self._get_delivery_rate()
            if vals.get('error_message'):
                raise UserError(vals['error_message'])
            _logger.info(
                'choose.delivery.carrier.button_confirm: refreshed rate for '
                'order %s carrier %s weight %.2f -> price %.2f',
                self.order_id.name, self.carrier_id.name,
                self.total_weight, self.delivery_price,
            )
        return super().button_confirm()
