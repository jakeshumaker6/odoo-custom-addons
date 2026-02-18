# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'POS Payment: JustiFi Terminal',
    'version': '19.0.1.0.1',
    'category': 'Sales/Point of Sale',
    'summary': 'Accept card payments via JustiFi terminals in Point of Sale.',
    'description': """
JustiFi Terminal Integration for Odoo Point of Sale
====================================================

This module integrates JustiFi payment terminals (Verifone E285) with Odoo POS,
allowing merchants to accept card-present payments through physical terminals.

Features:
- Send payment requests to JustiFi terminals from POS
- Real-time payment status updates via polling
- Multiple terminal support per POS
- Secure API communication

Configuration:
1. Go to Point of Sale → Configuration → Payment Methods
2. Create a new payment method with JustiFi terminal
3. Enter the Terminal ID (trm_xxxx)
4. Link the payment method to your POS configuration
    """,
    'author': 'Jake Shumaker at Pulse Marketing',
    'website': 'https://justifi.ai/',
    'depends': ['point_of_sale', 'payment_justifi'],
    'data': [
        'views/pos_payment_method_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_payment_justifi/static/src/js/**/*',
        ],
        'web.assets_backend': [
            'pos_payment_justifi/static/src/backend/**/*',
        ],
    },
    'application': False,
    'installable': True,
    'license': 'LGPL-3',
}
