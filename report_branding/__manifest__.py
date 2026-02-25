# -*- coding: utf-8 -*-
{
    'name': 'Report Branding',
    'version': '19.0.1.0.0',
    'summary': 'Larger logo on PDF reports (invoices, sales orders, etc.)',
    'description': """
Report Branding
===============

Makes the company logo larger on PDF reports:
- Invoices
- Sales Orders / Quotations
- Purchase Orders
- Any other PDF report using the standard layout
    """,
    'category': 'Technical',
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': ['web'],
    'assets': {
        'web.report_assets_common': [
            'report_branding/static/src/css/report_branding.css',
        ],
    },
    'installable': True,
    'auto_install': False,
}
