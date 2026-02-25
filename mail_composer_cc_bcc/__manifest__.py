# -*- coding: utf-8 -*-
{
    'name': 'Mail Composer CC/BCC',
    'version': '19.0.1.0.0',
    'summary': 'Add CC and BCC fields to email composer',
    'description': """
Mail Composer CC/BCC
====================

Adds CC (Carbon Copy) and BCC (Blind Carbon Copy) fields to the email
composer dialog. When sending emails from invoices, sales orders, or
any other document, you can now specify additional recipients.

Features:
- CC field in email composer
- BCC field in email composer
- Works with all email templates
- Optional - leave blank if not needed
    """,
    'category': 'Mail',
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': ['mail'],
    'data': [
        'views/mail_compose_message_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
