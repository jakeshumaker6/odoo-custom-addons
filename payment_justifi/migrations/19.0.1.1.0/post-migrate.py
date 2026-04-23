# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Post-migration for 19.0.1.1.0: enable refund support on payment methods
linked to the JustiFi provider.

The refund wizard (account_payment.payment_refund_wizard) takes the min
of provider.support_refund and payment_method.support_refund. The provider
compute now returns 'partial', but the pre-existing payment.method record
created by the 1.0.x post_init_hook has support_refund='none', which would
silently block the Refund button in the UI. This migration aligns the
payment method with the provider.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return  # fresh install path handled by _post_init_hook

    cr.execute("""
        UPDATE payment_method pm
           SET support_refund = 'partial'
          FROM payment_method_payment_provider_rel r
          JOIN payment_provider p ON p.id = r.payment_provider_id
         WHERE r.payment_method_id = pm.id
           AND p.code = 'justifi'
           AND pm.support_refund IS DISTINCT FROM 'partial'
        RETURNING pm.id, pm.code
    """)
    updated = cr.fetchall()
    if updated:
        _logger.info(
            "JustiFi migration 19.0.1.1.0: enabled partial refunds on payment methods %s",
            updated,
        )
