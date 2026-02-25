# -*- coding: utf-8 -*-
{
    'name': 'Subtotal Label',
    'version': '19.0.1.0.0',
    'summary': 'Change "Untaxed Amount" to "Subtotal" everywhere',
    'description': """
Subtotal Label
==============

Changes all instances of "Untaxed Amount" label to "Subtotal" in:
- Sales Orders / Quotations
- Invoices
- Purchase Orders
- Any document using tax_totals

This affects both the form view totals section and PDF reports.
    """,
    'category': 'Accounting',
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': ['account'],
    'installable': True,
    'auto_install': False,
}
