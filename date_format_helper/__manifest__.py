# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Date Format Helper',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': 'Auto-format date input for faster entry (type 021906 for 02/19/06)',
    'description': """
Date Format Helper
==================

Allows users to enter dates without typing separators.

Type numeric-only dates like:
- 021906 → 02/19/06
- 02192006 → 02/19/2006
- 2192006 → 2/19/2006 (single-digit month)

The module automatically inserts slashes as you type, making date entry
faster and more similar to QuickBooks Online.
    """,
    'author': 'Jake Shumaker at Pulse Marketing',
    'depends': ['web'],
    'assets': {
        'web.assets_backend': [
            'date_format_helper/static/src/js/date_auto_format.js',
        ],
    },
    'application': False,
    'installable': True,
    'license': 'LGPL-3',
}
