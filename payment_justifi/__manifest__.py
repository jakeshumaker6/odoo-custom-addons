# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Payment Provider: JustiFi',
    'version': '19.0.1.0.1',
    'category': 'Accounting/Payment Providers',
    'summary': 'Accept card payments via JustiFi payment processor.',
    'description': """
JustiFi Payment Provider for Odoo
=================================

This module integrates JustiFi as a payment provider in Odoo, allowing customers
to pay invoices using credit/debit cards through JustiFi's secure payment platform.

Features:
- Card payments via JustiFi modular checkout
- Secure tokenization (no card data stored in Odoo)
- Webhook support for real-time payment status updates
- Customer portal integration

Configuration:
1. Go to Invoicing → Configuration → Payment Providers
2. Select JustiFi and configure your API credentials
3. Set the provider state to Test or Enabled
    """,
    'author': 'Custom Integration',
    'website': 'https://justifi.ai/',
    'depends': ['payment', 'account', 'portal'],
    'data': [
        'views/payment_provider_views.xml',
        'views/payment_templates.xml',
        'data/payment_provider_data.xml',
    ],
    'application': False,
    'installable': True,
    'license': 'LGPL-3',
}
