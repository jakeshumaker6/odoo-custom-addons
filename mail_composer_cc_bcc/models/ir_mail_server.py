# -*- coding: utf-8 -*-
from odoo import models


class IrMailServer(models.Model):
    _inherit = 'ir.mail_server'

    def _build_email__(self, email_from, email_to, subject, body,
                       email_cc=None, email_bcc=None, reply_to=False,
                       attachments=None, message_id=None, references=None,
                       object_id=False, subtype='plain', headers=None,
                       body_alternative=None, subtype_alternative='plain'):
        """Inject Bcc from context when mail.mail._send routes a bcc-bearing
        record through build_email (Odoo's mail.mail._send signature omits
        email_bcc, so we propagate it via context: see MailMail._send)."""
        if not email_bcc:
            email_bcc = self.env.context.get('mail_bcc') or None
        return super()._build_email__(
            email_from=email_from,
            email_to=email_to,
            subject=subject,
            body=body,
            email_cc=email_cc,
            email_bcc=email_bcc,
            reply_to=reply_to,
            attachments=attachments,
            message_id=message_id,
            references=references,
            object_id=object_id,
            subtype=subtype,
            headers=headers,
            body_alternative=body_alternative,
            subtype_alternative=subtype_alternative,
        )
