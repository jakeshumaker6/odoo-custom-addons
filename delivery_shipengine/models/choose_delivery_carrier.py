# -*- coding: utf-8 -*-
import logging

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ChooseDeliveryCarrier(models.TransientModel):
    _inherit = 'choose.delivery.carrier'

    def write(self, vals):
        """Clear cached display_price / delivery_price whenever total_weight
        is changed on the wizard WITHOUT a concurrent display_price update.

        Why: ``total_weight`` is a related field to ``sale_order.shipping_weight``.
        When the user types a new weight in the wizard, Odoo's web client
        calls ``record.save({reload: true})`` before the Get rate button's
        RPC fires. That save commits only the dirty fields -- here, just
        ``total_weight``. The wizard's own ``display_price`` column in DB
        still holds the rate fetched for the PREVIOUS weight (e.g. $45.24
        from an earlier 80 lb fetch). The reload then pulls that stale
        value back onto the client, and the view renders it until the new
        API response arrives ~3 s later.

        By forcing display_price / delivery_price to 0 in the same write,
        the reload returns 0 and our view rule (added in 19.0.1.4.0) keeps
        the Cost field hidden through the entire RPC wait. Odoo's base view
        already hides the real Add button when display_price is 0 on
        API-based carriers, so the user also cannot commit a stale rate
        from that transient state.

        Guarded on ``'total_weight' in vals and 'display_price' not in vals``:
        only fires on user-driven weight changes. When ``_get_delivery_rate``
        writes display_price itself, that write includes display_price and
        is NOT intercepted. When Odoo writes unrelated fields (delivery_message,
        invoicing_message, etc.) total_weight isn't in vals and we don't touch
        anything.

        Scoped to API-based carriers only: fixed / base_on_rule carriers
        compute synchronously during onchange, so their cached price is
        never stale. Fall through to super for those.

        SAFETY NOTES: operates exclusively on ``choose.delivery.carrier``
        (a TransientModel that Odoo garbage-collects hourly). No writes to
        sale.order, res.partner, products, accounting, stock, or any other
        permanent model.
        """
        if 'total_weight' in vals and 'display_price' not in vals:
            for rec in self:
                if rec.delivery_type not in ('fixed', 'base_on_rule'):
                    vals['display_price'] = 0
                    vals['delivery_price'] = 0
                    break
        return super().write(vals)

    def button_confirm(self):
        """Re-fetch the rate for the CURRENT total_weight before committing
        the delivery line to the sale order. Defense-in-depth safety net
        that catches any path through which a stale price could reach
        ``self.delivery_price`` at the moment Add is clicked.

        The write() override above already prevents the UI flash of a
        stale price. This second override covers the data-integrity angle:
        whatever ``display_price`` / ``delivery_price`` happens to be on the
        record at click time, we re-run the API with the current total_weight
        and let super() use the freshly-computed value to set the SO's
        delivery line.

        One extra API call on every Add click (~3 s). No UI changes. No
        new fields. No migration.

        Only fires for API-based carriers (fixed / base_on_rule compute
        synchronously on onchange).
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
