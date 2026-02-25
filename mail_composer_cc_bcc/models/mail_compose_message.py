# -*- coding: utf-8 -*-
from odoo import models, fields


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    email_cc = fields.Char(
        string='Cc',
        help='Carbon copy recipients (comma-separated email addresses)',
    )

    def _prepare_mail_values(self, res_ids):
        """Override to include CC in the mail values."""
        results = super()._prepare_mail_values(res_ids)

        # Add CC to each mail being prepared
        if self.email_cc:
            for res_id in res_ids:
                if res_id in results:
                    # Combine any existing CC (from template) with composer CC
                    existing_cc = results[res_id].get('email_cc', '')
                    if existing_cc:
                        results[res_id]['email_cc'] = f"{existing_cc}, {self.email_cc}"
                    else:
                        results[res_id]['email_cc'] = self.email_cc

        return results
