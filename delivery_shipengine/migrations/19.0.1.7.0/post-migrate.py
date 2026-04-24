"""Populate shipengine_excluded_package_types on existing ShipEngine carriers.

The 19.0.1.7.0 release adds a new Char field to filter ShipEngine rates by
package_type. ShipEngine returns a rate for every flat-rate envelope/box
variant (USPS Priority Mail with package_type=flat_rate_envelope, or
small_flat_rate_box, medium_flat_rate_box, ...). These rates look cheap
(~$8.90 flat-rate envelope) because they don't scale with weight within
the 70 lb limit, but they're size-constrained to USPS-supplied packaging,
so they're inappropriate for general merchandise. The field default
excludes them; this migration backfills the default on rows that pre-date
the column.
"""
import logging

_logger = logging.getLogger(__name__)

DEFAULT_EXCLUDED_PACKAGE_TYPES = (
    'flat_rate_envelope,flat_rate_legal_envelope,flat_rate_padded_envelope,'
    'small_flat_rate_box,medium_flat_rate_box,large_flat_rate_box,'
    'regional_rate_box_a,regional_rate_box_b,regional_rate_box_c'
)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE delivery_carrier
           SET shipengine_excluded_package_types = %s
         WHERE delivery_type = 'shipengine'
           AND (shipengine_excluded_package_types IS NULL
                OR shipengine_excluded_package_types = '')
        """,
        (DEFAULT_EXCLUDED_PACKAGE_TYPES,),
    )
    _logger.info(
        'delivery_shipengine 19.0.1.7.0: backfilled excluded_package_types on %d carrier(s)',
        cr.rowcount,
    )
