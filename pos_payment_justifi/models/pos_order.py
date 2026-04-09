import logging
import re

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Names that indicate no real cardholder info was captured (tap, generic cards)
CARDHOLDER_BLOCKLIST = {
    'CARDHOLDER/VISA',
    'CARDHOLDER/MASTERCARD',
    'CARDHOLDER/AMEX',
    'CARDHOLDER/DISCOVER',
    'VALUED CUSTOMER',
    'CARD HOLDER',
    'VISA',
    'MASTERCARD',
    'AMEX',
    'DISCOVER',
}


def _parse_cardholder_name(raw_name):
    """Parse cardholder name from card chip data.

    Card chip typically returns LAST/FIRST format.
    Returns (first_name, last_name) tuple or False if invalid.
    """
    if not raw_name:
        return False

    cleaned = raw_name.strip()
    if not cleaned or cleaned.upper() in CARDHOLDER_BLOCKLIST:
        return False

    # Filter out single-word names or names with only special characters
    if len(cleaned) < 3 or not re.search(r'[a-zA-Z]', cleaned):
        return False

    # Handle LAST/FIRST format (card chip standard)
    if '/' in cleaned:
        parts = cleaned.split('/', 1)
        last_name = parts[0].strip().title()
        first_name = parts[1].strip().title() if len(parts) > 1 else ''
    else:
        # Space-separated: assume "First Last"
        parts = cleaned.strip().split()
        first_name = parts[0].title()
        last_name = ' '.join(parts[1:]).title() if len(parts) > 1 else ''

    if not last_name:
        return False

    return (first_name, last_name)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    justifi_cardholder_name = fields.Char(
        'Cardholder Name',
        readonly=True,
        help='Name from the card chip data (card insert only).',
    )
    justifi_customer_attributed = fields.Boolean(
        'Customer Auto-Attributed',
        default=False,
        help='True if the customer was auto-created/linked from card data.',
    )

    @api.model
    def create(self, vals):
        order = super().create(vals)
        # Attempt customer attribution after order creation
        if not order.partner_id:
            order._justifi_attribute_customer()
        return order

    def _justifi_attribute_customer(self):
        """Attempt to create/link a customer from JustiFi cardholder data.

        Called after order creation when no customer was selected.
        Only works for card-insert payments (not tap).
        """
        self.ensure_one()

        # Find JustiFi payment line with a payment_id
        justifi_payment = None
        for payment in self.payment_ids:
            if (payment.payment_method_id.use_payment_terminal == 'justifi'
                    and payment.transaction_id
                    and payment.transaction_id.startswith('py_')):
                justifi_payment = payment
                break

        if not justifi_payment:
            return

        payment_id = justifi_payment.transaction_id

        # Get the JustiFi provider
        provider = self.env['payment.provider'].sudo().search([
            ('code', '=', 'justifi'),
            ('state', '!=', 'disabled'),
        ], limit=1)

        if not provider:
            return

        # Fetch payment details from JustiFi API
        payment_data = provider._justifi_get_payment_details(payment_id)
        if not payment_data:
            return

        # Extract cardholder name
        card_data = payment_data.get('payment_method', {}).get('card', {})
        raw_name = card_data.get('name', '')

        # Store raw name for audit
        self.justifi_cardholder_name = raw_name

        parsed = _parse_cardholder_name(raw_name)
        if not parsed:
            _logger.info(
                'JustiFi attribution: name "%s" filtered out for order %s',
                raw_name, self.name,
            )
            return

        first_name, last_name = parsed
        full_name = f'{first_name} {last_name}'.strip()

        _logger.info(
            'JustiFi attribution: parsed "%s" → "%s" for order %s',
            raw_name, full_name, self.name,
        )

        # Search for existing partner by name
        Partner = self.env['res.partner'].sudo()
        domain = [('name', 'ilike', last_name), ('name', 'ilike', first_name)]
        existing = Partner.search(domain, order='write_date desc', limit=5)

        if len(existing) == 1:
            # Exact single match — link it
            partner = existing[0]
            _logger.info(
                'JustiFi attribution: matched existing partner %s (id=%s)',
                partner.name, partner.id,
            )
        elif len(existing) > 1:
            # Multiple matches — use most recently active
            partner = existing[0]
            _logger.info(
                'JustiFi attribution: %d matches for "%s", using most recent: %s (id=%s)',
                len(existing), full_name, partner.name, partner.id,
            )
        else:
            # No match — create new partner
            partner = Partner.create({
                'name': full_name,
                'customer_rank': 1,
            })
            _logger.info(
                'JustiFi attribution: created new partner "%s" (id=%s)',
                full_name, partner.id,
            )

        # Link partner to order
        self.write({
            'partner_id': partner.id,
            'justifi_customer_attributed': True,
        })
