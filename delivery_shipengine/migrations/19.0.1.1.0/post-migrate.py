"""Populate shipengine_excluded_service_codes on existing ShipEngine carriers.

The field was added in 19.0.1.1.0 with a default of 'usps_media_mail,usps_library_mail'
to stop Media Mail/Library Mail (restricted to books & educational media) from winning
the 'standard' tier on general shipments. Field defaults only apply to new records, so
this migration backfills existing ones that still have NULL / empty.
"""
import logging

_logger = logging.getLogger(__name__)

DEFAULT_EXCLUSIONS = 'usps_media_mail,usps_library_mail'


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE delivery_carrier
           SET shipengine_excluded_service_codes = %s
         WHERE delivery_type = 'shipengine'
           AND (shipengine_excluded_service_codes IS NULL
                OR shipengine_excluded_service_codes = '')
    """, (DEFAULT_EXCLUSIONS,))
    _logger.info(
        'delivery_shipengine 19.0.1.1.0: backfilled excluded_service_codes on %d carrier(s)',
        cr.rowcount,
    )
