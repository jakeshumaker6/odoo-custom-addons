"""Remove the obsolete Studio view and manual fields (x_email_cc, x_email_bcc)
on mail.compose.message.

Before this module was written, someone added x_email_cc and x_email_bcc as
Studio/manual fields on the mail composer along with a form view inheriting
the composer to display them. The fields had no business logic attached -- the
values were dropped on the floor. After we shipped mail_composer_cc_bcc with
real email_cc + email_bcc fields (plus _action_send_mail / mail.mail._send
wiring), the Studio fields became dead weight, still firing a field-label
collision warning at every module load:

    WARNING: Two fields (x_email_cc, email_cc) of mail.compose.message()
    have the same label: Cc.

This migration removes them. Uses the ORM so column drops happen cleanly.
Idempotent: runs find-and-delete, no-op if the Studio records are already gone.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1) Find the obsolete Studio composer view: no xmlid + references x_email_*
    cr.execute("""
        SELECT v.id
          FROM ir_ui_view v
          LEFT JOIN ir_model_data d
                 ON d.model = 'ir.ui.view' AND d.res_id = v.id
         WHERE v.model = 'mail.compose.message'
           AND v.type = 'form'
           AND v.arch_db::text ~ '(x_email_cc|x_email_bcc)'
           AND d.id IS NULL
    """)
    view_ids = [row[0] for row in cr.fetchall()]

    # 2) Find the obsolete manual fields
    cr.execute("""
        SELECT id
          FROM ir_model_fields
         WHERE model = 'mail.compose.message'
           AND name IN ('x_email_cc', 'x_email_bcc')
           AND state = 'manual'
    """)
    field_ids = [row[0] for row in cr.fetchall()]

    if view_ids:
        env['ir.ui.view'].browse(view_ids).unlink()
        _logger.info(
            'mail_composer_cc_bcc 19.0.1.1.0: removed %d obsolete Studio composer view(s): %s',
            len(view_ids), view_ids,
        )

    if field_ids:
        # ir.model.fields unlink drops the underlying column automatically
        env['ir.model.fields'].browse(field_ids).unlink()
        _logger.info(
            'mail_composer_cc_bcc 19.0.1.1.0: removed %d obsolete manual field(s): %s',
            len(field_ids), field_ids,
        )

    # 3) Belt-and-suspenders: clean any ir_model_data pointing at now-removed
    #    fields or view (ORM unlink should handle this, but Studio-stamped
    #    entries sometimes resist cascade).
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE model = 'ir.model.fields'
           AND name IN ('field_mail_compose_message__x_email_cc',
                        'field_mail_compose_message__x_email_bcc')
    """)
    if cr.rowcount:
        _logger.info(
            'mail_composer_cc_bcc 19.0.1.1.0: cleaned %d residual ir_model_data row(s)',
            cr.rowcount,
        )
