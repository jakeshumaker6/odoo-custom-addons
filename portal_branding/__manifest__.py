# -*- coding: utf-8 -*-
{
    'name': 'Portal Branding',
    'version': '19.0.1.0.0',
    'summary': 'Custom branding for customer portal',
    'description': """
Portal Branding - South Forty Specialties
==========================================

Customizes the customer portal appearance:
- Larger company logo
- Orange brand buttons (#CC6118)
- Matching accent colors
- Consistent branding throughout portal
    """,
    'category': 'Website',
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': ['portal', 'web'],
    'assets': {
        'web.assets_frontend': [
            'portal_branding/static/src/css/portal_branding.css',
        ],
    },
    'installable': True,
    'auto_install': False,
}
