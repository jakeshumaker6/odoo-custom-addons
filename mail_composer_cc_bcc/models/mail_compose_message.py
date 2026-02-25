# -*- coding: utf-8 -*-
from odoo import models, fields, api


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    email_cc = fields.Char(
        string='Cc',
        help='Carbon copy recipients (comma-separated email addresses)',
    )

    def _action_send_mail(self, auto_commit=False):
        """Override to pass CC via context to mail.mail creation."""
        # Pass the CC via context so mail.mail can pick it up
        if self.email_cc:
            self = self.with_context(composer_email_cc=self.email_cc)
        return super()._action_send_mail(auto_commit=auto_commit)


class MailMail(models.Model):
    _inherit = 'mail.mail'

    @api.model_create_multi
    def create(self, vals_list):
        """Override to add CC from composer context."""
        composer_cc = self.env.context.get('composer_email_cc')
        if composer_cc:
            for vals in vals_list:
                existing_cc = vals.get('email_cc', '')
                if existing_cc:
                    vals['email_cc'] = f"{existing_cc}, {composer_cc}"
                else:
                    vals['email_cc'] = composer_cc
        return super().create(vals_list)
