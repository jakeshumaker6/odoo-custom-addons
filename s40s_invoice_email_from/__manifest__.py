# -*- coding: utf-8 -*-
{
    'name': 'S40S Invoice Email From',
    'version': '19.0.1.0.0',
    'summary': 'Send all customer invoices and credit notes from the company email (finance@s40s.com)',
    'description': """
S40S Invoice Email From
=======================

Stock Odoo resolves the From address on invoice/credit-note emails using this priority:
    1. Salesperson's email (object.invoice_user_id.email_formatted)
    2. Company email (object.company_id.email_formatted)
    3. Sending user's email (user.email_formatted)

This means invoices appeared to customers as coming from whichever salesperson was assigned,
which for S40S meant some invoices arrived from individual user mailboxes instead of the
shared finance address.

This module narrows the From expression on the customer Invoice and Credit Note email
templates to ONLY use the company email, so all customer-facing AR mail is consistent
regardless of who is assigned as Salesperson or who clicks Send.

The Salesperson field on the invoice itself is unchanged — it remains accurate for
reporting and customer relationship tracking.

Setup requirement:
- The S40S company record must have its Email field set to finance@s40s.com
  (Settings -> Companies -> South 40 Specialties -> Email)
    """,
    'category': 'Accounting/Accounting',
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'data/mail_template_data.xml',
    ],
    'installable': True,
    'auto_install': False,
}
