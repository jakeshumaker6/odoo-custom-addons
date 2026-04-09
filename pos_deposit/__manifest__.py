{
    'name': 'POS Customer Deposits',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Collect and redeem $500 customer deposits in POS',
    'description': """
Adds deposit collection and redemption to the Point of Sale.
- Collect $500 non-refundable, non-expiring deposits
- Track deposits per customer
- Redeem deposits against future orders
- Deposits post to a liability account (not revenue)
    """,
    'author': 'Pulse Integrated',
    'website': 'https://pulseintegrated.com',
    'depends': ['point_of_sale', 'account'],
    'data': [
        'data/account_data.xml',
        'data/product_data.xml',
        'views/pos_order_views.xml',
        'views/res_partner_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_deposit/static/src/**/*',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
