# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import controllers


def _post_init_hook(env):
    """
    Link JustiFi provider to a single payment method that handles both Card and ACH.
    The JustiFi web component internally handles card vs bank account selection.
    """
    # Find the JustiFi provider
    provider = env['payment.provider'].search([('code', '=', 'justifi')], limit=1)
    if not provider:
        return

    # Find or create a JustiFi payment method (handles both card and ACH)
    # We use bank_sepa code but name it to reflect both options
    justifi_method = env['payment.method'].search([('code', '=', 'bank_sepa')], limit=1)
    if justifi_method:
        # Ensure JustiFi is linked and name is correct
        updates = {}
        if provider not in justifi_method.provider_ids:
            updates['provider_ids'] = [(4, provider.id)]
        if 'JustiFi' not in justifi_method.name:
            updates['name'] = 'JustiFi (Card / ACH)'
        if updates:
            justifi_method.write(updates)
    else:
        # Create the payment method
        env['payment.method'].create({
            'name': 'JustiFi (Card / ACH)',
            'code': 'bank_sepa',
            'sequence': 20,
            'active': True,
            'provider_ids': [(4, provider.id)],
        })

    # Remove JustiFi from Card payment method if present (avoid duplicate options)
    card_method = env['payment.method'].search([('code', '=', 'card')], limit=1)
    if card_method and provider in card_method.provider_ids:
        card_method.write({'provider_ids': [(3, provider.id)]})
