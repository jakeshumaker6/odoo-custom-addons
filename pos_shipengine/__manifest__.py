{
    'name': 'POS ShipEngine Shipping Rates',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'ShipEngine shipping rate selection in POS Ship Later flow',
    'description': """
Adds shipping rate selection to the POS payment screen when Ship Later is enabled.
Fetches real-time rates from ShipEngine, groups them into Express/Standard/Economy
tiers, and allows custom shipping amounts. Creates shipping labels for fulfillment.
    """,
    'author': 'Pulse Integrated',
    'website': 'https://pulseintegrated.com',
    'depends': ['point_of_sale', 'delivery_shipengine'],
    'data': [
        'views/pos_config_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_shipengine/static/src/**/*',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
