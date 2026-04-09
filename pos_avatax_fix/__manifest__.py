# -*- coding: utf-8 -*-
{
    'name': 'POS AvaTax Fix',
    'version': '19.0.1.1.0',
    'summary': 'Fix AvaTax for POS: warehouse-based tax for Take Now, customer address for Ship Later',
    'description': """
POS AvaTax Fix
==============

- Adds partner_shipping_id computed field to pos.order
- Take Now orders: tax based on POS warehouse location
- Ship Later orders: tax based on customer shipping address
- Handles incomplete/missing customer addresses gracefully
- Allows AvaTax calculation even without a customer selected
    """,
    'category': 'Point of Sale',
    'author': 'Pulse Integrated',
    'license': 'LGPL-3',
    'depends': ['pos_avatax'],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_avatax_fix/static/src/**/*',
        ],
    },
    'installable': True,
    'auto_install': True,
}
