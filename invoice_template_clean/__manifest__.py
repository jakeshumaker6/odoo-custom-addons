# -*- coding: utf-8 -*-
{
    'name': 'Invoice Template Clean',
    'version': '19.0.1.0.0',
    'summary': 'Cleaner invoice labels for tax-exempt customers',
    'description': """
Invoice Template Clean
======================

Improves invoice PDF readability:
- Changes "Untaxed Amount" to "Subtotal"
- Hides tax lines when the tax amount is zero (for tax-exempt invoices)

This provides a cleaner look for invoices sent to tax-exempt customers.
    """,
    'category': 'Accounting/Accounting',
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'views/report_invoice_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
}
