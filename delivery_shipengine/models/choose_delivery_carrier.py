# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError


class ChooseDeliveryCarrier(models.TransientModel):
    _inherit = 'choose.delivery.carrier'

    def update_price(self):
        """Override the base wizard so that after fetching a new rate we
        refresh the current dialog in place instead of closing + reopening it.

        The base method returns an ``ir.actions.act_window`` with
        ``target='new'``. That closes the currently-open dialog and opens a
        fresh one. During the brief re-open the client renders the last
        client-cached state of the wizard, which includes the PREVIOUS
        display_price (e.g. the 10 lb rate) — it only updates to the real
        new value once the fresh record fetch completes. Reads as a "stale
        price flashes, then updates" UX.

        Returning ``None`` (or ``True``) instead keeps the dialog open and
        lets the form's normal field re-render pick up the server-set
        display_price / delivery_price without a dialog recycle.

        Tradeoff: we lose the ``no_rate`` context flag the base method sets
        on its act_window, which the view uses to swap ``delivery_message``
        between an info (blue) and danger (red) alert when no rates are
        available. Without it, the alert stays in the info variant. The
        message text itself still conveys the state; acceptable for our
        use case.
        """
        vals = self._get_delivery_rate()
        if vals.get('error_message'):
            raise UserError(vals['error_message'])
        return None
