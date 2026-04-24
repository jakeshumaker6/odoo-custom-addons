"""Clean up residual Studio x_email_* manual fields across mail.* models.

The 19.0.1.1.0 migration only targeted mail.compose.message. Production
still had an x_email_bcc manual field on mail.mail (id 21709) along
with its ir_model_data stamp, causing a label-collision WARNING on
every module load:

    WARNING: Two fields (x_email_bcc, email_bcc) of mail.mail() have
    the same label: Bcc. [Modules: None and mail_composer_cc_bcc]

This migration generalizes the cleanup: any manual `x_email_*` field on
any `mail.*` model whose label collides with a proper field from our
module (or from upstream) is removed. Also sweeps any orphan Studio
views (no xmlid) that reference x_email_* on these models.

Conservative: only touches `state='manual'` fields and only views
without an ir_model_data (xmlid) entry.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

TARGET_FIELD_NAMES = ('x_email_cc', 'x_email_bcc', 'x_email_to')


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1) Manual x_email_* fields on any mail.* model
    cr.execute(
        """
        SELECT id, model, name
          FROM ir_model_fields
         WHERE model LIKE 'mail.%%'
           AND name = ANY(%s)
           AND state = 'manual'
        """,
        (list(TARGET_FIELD_NAMES),),
    )
    rows = cr.fetchall()
    field_ids = [r[0] for r in rows]

    # 2) Orphan Studio views (no xmlid) that reference any of these field names
    like_patterns = '|'.join(TARGET_FIELD_NAMES)
    cr.execute(
        """
        SELECT v.id, v.model
          FROM ir_ui_view v
          LEFT JOIN ir_model_data d
                 ON d.model = 'ir.ui.view' AND d.res_id = v.id
         WHERE v.model LIKE 'mail.%%'
           AND v.arch_db::text ~ %s
           AND d.id IS NULL
        """,
        (like_patterns,),
    )
    view_rows = cr.fetchall()
    view_ids = [r[0] for r in view_rows]

    if view_ids:
        env['ir.ui.view'].browse(view_ids).unlink()
        _logger.info(
            'mail_composer_cc_bcc 19.0.1.2.0: removed %d orphan Studio view(s) referencing x_email_*: %s',
            len(view_ids), view_rows,
        )

    if field_ids:
        env['ir.model.fields'].browse(field_ids).unlink()
        _logger.info(
            'mail_composer_cc_bcc 19.0.1.2.0: removed %d residual manual x_email_* field(s): %s',
            len(field_ids), rows,
        )

    # 3) Residual ir_model_data entries that pointed at these fields
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE model = 'ir.model.fields'
           AND (
               name LIKE 'field_mail_%%__x_email_cc'
            OR name LIKE 'field_mail_%%__x_email_bcc'
            OR name LIKE 'field_mail_%%__x_email_to'
           )
        """
    )
    if cr.rowcount:
        _logger.info(
            'mail_composer_cc_bcc 19.0.1.2.0: cleaned %d residual ir_model_data row(s)',
            cr.rowcount,
        )
