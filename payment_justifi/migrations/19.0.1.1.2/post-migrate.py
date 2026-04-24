# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Post-migration for 19.0.1.1.2: broaden refund-enablement to cover
payment methods referenced by HISTORICAL JustiFi transactions that are
no longer (or never were) listed in payment_method_payment_provider_rel.

Why this exists
---------------
The 1.1.0 migration updated every payment.method currently linked to
the JustiFi provider via the rel table. That correctly caught the
"JustiFi (Card / ACH)" bank_sepa method, but on this install an
orphan duplicate ``code='card'`` payment.method (id 214) exists: it
was the original card method attached to JustiFi by an earlier
version of _post_init_hook, then the hook unlinked it to avoid a
duplicate checkout option. The unlinking did not touch historical
payment.transaction rows, so 27 of 28 existing JustiFi transactions
still point at it — and the refund wizard's compute reads
``tx.payment_method_id.support_refund`` directly, ignoring the
provider rel table. Result: Refund button stays hidden on every
legacy payment until that orphan row is fixed.

This migration catches it by joining through payment_transaction
instead of payment_method_payment_provider_rel, so any method that
JustiFi has ever used is aligned.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return  # fresh install path handled by _post_init_hook

    cr.execute("""
        UPDATE payment_method pm
           SET support_refund = 'partial'
         WHERE pm.id IN (
                SELECT DISTINCT t.payment_method_id
                  FROM payment_transaction t
                  JOIN payment_provider p ON p.id = t.provider_id
                 WHERE p.code = 'justifi'
                   AND t.payment_method_id IS NOT NULL
             )
           AND pm.support_refund IS DISTINCT FROM 'partial'
        RETURNING pm.id, pm.code
    """)
    updated = cr.fetchall()
    if updated:
        _logger.info(
            "JustiFi migration 19.0.1.1.2: enabled partial refunds on "
            "historical-transaction payment methods %s",
            updated,
        )
