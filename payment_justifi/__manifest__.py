# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Payment Provider: JustiFi',
    'version': '19.0.1.0.21',
    'category': 'Accounting/Payment Providers',
    'summary': 'Accept card and ACH payments via JustiFi payment processor.',
    'description': """
JustiFi Payment Provider for Odoo
=================================

This module integrates JustiFi as a payment provider in Odoo, allowing customers
to pay invoices using credit/debit cards or ACH bank transfers through JustiFi's secure payment platform.

Features:
- Card payments via JustiFi modular checkout
- ACH/bank account payments
- Configurable payment methods (Card, ACH, or Both)
- Per-invoice payment method selection
- Secure tokenization (no card data stored in Odoo)
- Webhook support for real-time payment status updates
- Customer portal integration

Configuration:
1. Go to Invoicing → Configuration → Payment Providers
2. Select JustiFi and configure your API credentials
3. Set the provider state to Test or Enabled
    """,
    'author': 'Jake Shumaker at Pulse Marketing',
    'website': 'https://justifi.ai/',
    'depends': ['payment', 'account', 'portal'],
    'data': [
        'views/payment_provider_views.xml',
        'views/account_move_views.xml',
        'views/payment_templates.xml',
        'data/payment_provider_data.xml',
    ],
    'application': False,
    'installable': True,
    'license': 'LGPL-3',
}
