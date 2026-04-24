{
    'name': 'ShipEngine Shipping',
    'version': '19.0.1.4.0',
    'category': 'Inventory/Delivery',
    'summary': 'Ship via ShipEngine — multi-carrier rate shopping, label printing, and tracking',
    'description': """
ShipEngine delivery carrier integration for Odoo 19.
Supports rate shopping across USPS, UPS, FedEx, and other carriers.
Includes label generation and tracking.
    """,
    'author': 'Pulse Integrated',
    'website': 'https://pulseintegrated.com',
    'depends': ['delivery', 'stock'],
    'data': [
        'views/delivery_carrier_views.xml',
        'views/choose_delivery_carrier_views.xml',
        'data/delivery_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
