# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import controllers


def _post_init_hook(env):
    """
    Link JustiFi provider to Card and Bank payment methods after installation.
    This ensures ACH/bank payments are available alongside card payments.
    """
    # Find the JustiFi provider
    provider = env['payment.provider'].search([('code', '=', 'justifi')], limit=1)
    if not provider:
        return

    # Find and link Card payment method
    card_method = env['payment.method'].search([('code', '=', 'card')], limit=1)
    if card_method and provider not in card_method.provider_ids:
        card_method.write({'provider_ids': [(4, provider.id)]})

    # Find and link Bank/ACH payment method (try multiple codes)
    for bank_code in ['bank_sepa', 'sepa', 'bank']:
        bank_method = env['payment.method'].search([('code', '=', bank_code)], limit=1)
        if bank_method:
            if provider not in bank_method.provider_ids:
                bank_method.write({'provider_ids': [(4, provider.id)]})
            break
    else:
        # If no bank method exists, create one for ACH
        env['payment.method'].create({
            'name': 'Bank Account / ACH',
            'code': 'bank_sepa',
            'sequence': 20,
            'active': True,
            'provider_ids': [(4, provider.id)],
        })
