# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    email_cc = fields.Char(
        string='Cc',
        help='Carbon copy recipients (comma-separated email addresses).',
    )
    email_bcc = fields.Char(
        string='Bcc',
        help='Blind carbon copy recipients (comma-separated email addresses). '
             'Recipients in To/Cc do not see these addresses.',
    )

    def _action_send_mail(self, auto_commit=False):
        """Route Cc and Bcc via context so mail.mail.create can stamp them
        onto the mail.mail records it builds."""
        ctx_updates = {}
        if self.email_cc:
            ctx_updates['composer_email_cc'] = self.email_cc
        if self.email_bcc:
            ctx_updates['composer_email_bcc'] = self.email_bcc
        if ctx_updates:
            self = self.with_context(**ctx_updates)
        return super()._action_send_mail(auto_commit=auto_commit)


class MailMail(models.Model):
    _inherit = 'mail.mail'

    email_bcc = fields.Char(
        'Bcc',
        help='Blind carbon copy message recipients.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Stamp Cc / Bcc from composer context onto new mail.mail records."""
        composer_cc = self.env.context.get('composer_email_cc')
        composer_bcc = self.env.context.get('composer_email_bcc')
        if composer_cc or composer_bcc:
            for vals in vals_list:
                if composer_cc:
                    existing = vals.get('email_cc') or ''
                    vals['email_cc'] = f'{existing}, {composer_cc}' if existing else composer_cc
                if composer_bcc:
                    existing = vals.get('email_bcc') or ''
                    vals['email_bcc'] = f'{existing}, {composer_bcc}' if existing else composer_bcc
        return super().create(vals_list)

    def _send(self, *args, **kwargs):
        """For each mail with Bcc set, call super under a context that
        ir.mail_server._build_email__ can read to inject the Bcc header.

        Iterates per-record only when Bcc is present; otherwise preserves
        upstream batching via a single super() call on the non-Bcc subset.
        """
        if not self:
            return super()._send(*args, **kwargs)

        with_bcc = self.filtered('email_bcc')
        without_bcc = self - with_bcc

        result = None
        if without_bcc:
            result = super(MailMail, without_bcc)._send(*args, **kwargs)
        for mail in with_bcc:
            super(MailMail, mail.with_context(mail_bcc=mail.email_bcc))._send(*args, **kwargs)
        return result
