# -*- coding: utf-8 -*-
{
    'name': 'Sale Down Payment Description',
    'version': '19.0.1.0.0',
    'summary': 'Include product names in down payment invoice descriptions',
    'description': """
Sale Down Payment Description
=============================

This module enhances down payment invoice line descriptions by automatically
including the product names from the associated Sales Order.

Features:
- Automatically lists products from the Sales Order in down payment descriptions
- Shows up to 5 product names, with a count for additional items
- Includes the Sales Order reference number
- Works with both fixed amount and percentage down payments

Example output:
    "Deposit (50%) for: Product A, Product B, Product C
    Order: S00001"
    """,
    'category': 'Sales/Sales',
    'author': 'Custom',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['sale'],
    'data': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
