# -*- coding: utf-8 -*-
{
    'name': 'POS AvaTax Fix',
    'version': '19.0.1.0.0',
    'summary': 'Add missing partner_shipping_id to pos.order for AvaTax compatibility',
    'description': """
POS AvaTax Fix
==============

Fixes AttributeError: 'pos.order' object has no attribute 'partner_shipping_id'

The account_avatax mixin references partner_shipping_id in _get_avatax_service_params(),
but pos.order does not define this field. This module adds it as a computed field
that resolves the customer's delivery address.
    """,
    'category': 'Point of Sale',
    'author': 'Pulse Integrated',
    'license': 'LGPL-3',
    'depends': ['pos_avatax'],
    'installable': True,
    'auto_install': True,
}
