# -*- coding: utf-8 -*-
from odoo import models, fields


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    email_cc = fields.Char(
        string='Cc',
        help='Carbon copy recipients (comma-separated email addresses)',
    )

    def _action_send_mail(self, auto_commit=False):
        """Override to add CC to sent emails."""
        # Store CC before sending
        cc_to_add = self.email_cc

        # Call parent to send the mail
        result = super()._action_send_mail(auto_commit=auto_commit)

        # If CC was specified, update the mail.mail records that were just created
        if cc_to_add and result:
            mails, messages = result
            if mails:
                for mail in mails:
                    # Combine with any existing CC (from template)
                    existing_cc = mail.email_cc or ''
                    if existing_cc:
                        mail.email_cc = f"{existing_cc}, {cc_to_add}"
                    else:
                        mail.email_cc = cc_to_add

        return result
