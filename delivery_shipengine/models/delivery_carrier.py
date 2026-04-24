import json
import logging
import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SHIPENGINE_API_URL = 'https://api.shipengine.com'


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(
        selection_add=[('shipengine', 'ShipEngine')],
        ondelete={'shipengine': lambda recs: recs.write({
            'delivery_type': 'fixed', 'fixed_price': 0,
        })},
    )

    shipengine_api_key = fields.Char(
        string='ShipEngine API Key',
        groups='base.group_system',
    )
    shipengine_carrier_ids = fields.Char(
        string='ShipEngine Carrier IDs',
        help='Comma-separated ShipEngine carrier IDs (e.g., "se-123456,se-789012"). '
             'Leave blank to use all carriers on your account.',
    )
    shipengine_default_weight_oz = fields.Float(
        string='Default Item Weight (oz)',
        default=16.0,
        help='Fallback weight per item when product weight is not set.',
    )
    shipengine_default_package_code = fields.Char(
        string='Default Package Code',
        default='package',
        help='ShipEngine package code (e.g., "package", "flat_rate_envelope").',
    )
    shipengine_label_format = fields.Selection([
        ('pdf', 'PDF'),
        ('png', 'PNG'),
        ('zpl', 'ZPL'),
    ], string='Label Format', default='pdf')
    shipengine_excluded_service_codes = fields.Char(
        string='Excluded Service Codes',
        default='usps_media_mail,usps_library_mail',
        help='Comma-separated ShipEngine service_codes to exclude from rate shopping. '
             'USPS Media Mail and Library Mail are restricted to books/educational media '
             'and should not be used for general goods. Add other restricted services here.',
    )

    # ─── Helpers ───────────────────────────────────────────────

    def _shipengine_excluded_set(self):
        """Return the set of excluded service_codes for this carrier."""
        self.ensure_one()
        raw = self.shipengine_excluded_service_codes or ''
        return {code.strip() for code in raw.split(',') if code.strip()}

    def _shipengine_api_key_get(self):
        """Return the API key, raising if not configured."""
        self.ensure_one()
        key = self.sudo().shipengine_api_key
        if not key:
            raise UserError(_('ShipEngine API key is not configured on carrier "%s".', self.name))
        return key

    def _shipengine_request(self, method, endpoint, payload=None):
        """Make an authenticated request to the ShipEngine API."""
        self.ensure_one()
        url = f'{SHIPENGINE_API_URL}{endpoint}'
        headers = {
            'API-Key': self._shipengine_api_key_get(),
            'Content-Type': 'application/json',
        }
        _logger.info('ShipEngine %s %s', method.upper(), endpoint)
        try:
            resp = requests.request(method, url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as exc:
            body = {}
            try:
                body = exc.response.json()
            except Exception:
                pass
            errors = body.get('errors', [])
            msg = errors[0].get('message', str(exc)) if errors else str(exc)
            _logger.error('ShipEngine error: %s', msg)
            raise UserError(_('ShipEngine API error: %s', msg)) from exc
        except requests.exceptions.RequestException as exc:
            _logger.error('ShipEngine connection error: %s', exc)
            raise UserError(_('Could not connect to ShipEngine: %s', exc)) from exc

    # ─── Address Helpers ───────────────────────────────────────

    @staticmethod
    def _shipengine_format_address(partner):
        """Format an Odoo partner into a ShipEngine address dict."""
        # ShipEngine requires phone — use a placeholder if missing.
        # Odoo 18+ removed res.partner.mobile; use getattr so older installs still work.
        phone = partner.phone or getattr(partner, 'mobile', None) or ''
        if not phone and partner.parent_id:
            phone = partner.parent_id.phone or getattr(partner.parent_id, 'mobile', None) or ''
        if not phone:
            phone = '0000000000'

        return {
            'name': partner.name or '',
            'phone': phone,
            'address_line1': partner.street or '',
            'address_line2': partner.street2 or '',
            'city_locality': partner.city or '',
            'state_province': partner.state_id.code if partner.state_id else '',
            'postal_code': partner.zip or '',
            'country_code': partner.country_id.code if partner.country_id else 'US',
        }

    # ─── Package / Weight ──────────────────────────────────────

    def _shipengine_compute_packages(self, order_lines=None, picking=None):
        """Compute package list from order lines or picking.
        Returns a list of ShipEngine package dicts.
        """
        self.ensure_one()
        total_weight_oz = 0.0

        if order_lines:
            for line in order_lines:
                product = line.product_id
                qty = line.product_uom_qty if hasattr(line, 'product_uom_qty') else line.qty
                if product.weight:
                    # Odoo stores weight in kg by default; convert to oz
                    total_weight_oz += product.weight * 35.274 * qty
                else:
                    total_weight_oz += self.shipengine_default_weight_oz * qty
        elif picking:
            for move in picking.move_ids:
                if move.product_id.weight:
                    total_weight_oz += move.product_id.weight * 35.274 * move.quantity
                else:
                    total_weight_oz += self.shipengine_default_weight_oz * move.quantity

        total_weight_oz = max(total_weight_oz, 1.0)  # minimum 1 oz

        return [{
            'weight': {
                'value': round(total_weight_oz, 1),
                'unit': 'ounce',
            },
            'package_code': self.shipengine_default_package_code or 'package',
        }]

    # ─── Rate Shopping ─────────────────────────────────────────

    def _shipengine_get_rates_raw(self, ship_from_partner, ship_to_partner, packages):
        """Call ShipEngine /v1/rates and return raw rate list."""
        self.ensure_one()
        payload = {
            'rate_options': {
                'carrier_ids': [
                    cid.strip()
                    for cid in (self.shipengine_carrier_ids or '').split(',')
                    if cid.strip()
                ],
            },
            'shipment': {
                'ship_from': self._shipengine_format_address(ship_from_partner),
                'ship_to': self._shipengine_format_address(ship_to_partner),
                'packages': packages,
            },
        }

        # If no carrier_ids configured, remove the key so SE uses all account carriers
        if not payload['rate_options']['carrier_ids']:
            payload['rate_options'].pop('carrier_ids', None)

        data = self._shipengine_request('POST', '/v1/rates', payload)
        rate_response = data.get('rate_response', {})
        rates = rate_response.get('rates', [])
        errors = rate_response.get('errors', [])

        if errors and not rates:
            error_msgs = [e.get('message', '') for e in errors]
            _logger.warning('ShipEngine rate errors: %s', error_msgs)

        return rates

    @staticmethod
    def _shipengine_filter_rates(rates, excluded_service_codes=None):
        """Drop rates whose service_code is in the excluded set."""
        excluded = set(excluded_service_codes or [])
        if not excluded:
            return list(rates)
        return [r for r in rates if r.get('service_code', '') not in excluded]

    @staticmethod
    def _shipengine_group_rates_into_tiers(rates, excluded_service_codes=None):
        """Group raw ShipEngine rates into Express / Standard / Economy tiers.

        Returns a list of dicts:
            [{tier, carrier_name, service_type, rate_id, amount, delivery_days, estimated_delivery}]

        Tier logic:
            Express  = cheapest rate with delivery_days < 5
            Standard = cheapest rate with 5 <= delivery_days <= 7
            Economy  = cheapest rate with delivery_days > 7

        Rates whose service_code appears in ``excluded_service_codes`` are skipped.
        Callers should pass the carrier's blacklist (e.g. USPS Media Mail) to avoid
        surfacing service codes that are restricted to specific goods.
        """
        excluded = set(excluded_service_codes or [])
        buckets = {'express': [], 'standard': [], 'economy': []}

        for rate in rates:
            if rate.get('service_code', '') in excluded:
                continue
            amount = float(rate.get('shipping_amount', {}).get('amount', 0))
            days = rate.get('delivery_days')
            if days is None or amount <= 0:
                continue

            entry = {
                'carrier_name': rate.get('carrier_friendly_name', rate.get('carrier_id', '')),
                'service_type': rate.get('service_type', ''),
                'service_code': rate.get('service_code', ''),
                'rate_id': rate.get('rate_id', ''),
                'amount': amount,
                'delivery_days': days,
                'estimated_delivery': rate.get('estimated_delivery_date', ''),
            }

            if days < 5:
                buckets['express'].append(entry)
            elif days <= 7:
                buckets['standard'].append(entry)
            else:
                buckets['economy'].append(entry)

        result = []
        for tier_name, entries in buckets.items():
            if entries:
                cheapest = min(entries, key=lambda e: e['amount'])
                cheapest['tier'] = tier_name
                result.append(cheapest)

        return sorted(result, key=lambda r: r['delivery_days'])

    def shipengine_get_all_rates(self, ship_to_partner, order_lines=None, picking=None):
        """Get all tiered shipping rates for a destination.

        Used by POS and Sales modules to present rate options.
        Returns: list of tier dicts + raw rates for debugging.
        """
        self.ensure_one()
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id or self.env.company.id)], limit=1,
        )
        if not warehouse or not warehouse.partner_id:
            raise UserError(_('No warehouse configured for carrier "%s".', self.name))

        packages = self._shipengine_compute_packages(order_lines=order_lines, picking=picking)
        raw_rates = self._shipengine_get_rates_raw(warehouse.partner_id, ship_to_partner, packages)
        excluded = self._shipengine_excluded_set()
        tiers = self._shipengine_group_rates_into_tiers(raw_rates, excluded_service_codes=excluded)

        return {
            'tiers': tiers,
            'raw_rate_count': len(raw_rates),
            'excluded_count': sum(1 for r in raw_rates if r.get('service_code', '') in excluded),
        }

    # ─── Standard Odoo Carrier Methods ─────────────────────────

    def shipengine_rate_shipment(self, order):
        """Standard Odoo rate_shipment dispatch method.
        Returns the cheapest available rate.
        """
        self.ensure_one()
        try:
            ship_to = order.partner_shipping_id or order.partner_id
            result = self.shipengine_get_all_rates(ship_to, order_lines=order.order_line)
            tiers = result.get('tiers', [])

            if not tiers:
                return {
                    'success': False,
                    'price': 0.0,
                    'error_message': _('No shipping rates available for this destination.'),
                    'warning_message': False,
                }

            cheapest = min(tiers, key=lambda t: t['amount'])
            return {
                'success': True,
                'price': cheapest['amount'],
                'error_message': False,
                'warning_message': False,
            }

        except UserError as exc:
            return {
                'success': False,
                'price': 0.0,
                'error_message': str(exc),
                'warning_message': False,
            }

    def shipengine_send_shipping(self, pickings):
        """Create shipping labels via ShipEngine.
        Returns list of dicts with tracking info per picking.
        """
        self.ensure_one()
        results = []

        for picking in pickings:
            ship_to = picking.partner_id
            ship_from = picking.picking_type_id.warehouse_id.partner_id
            if not ship_from:
                ship_from = picking.company_id.partner_id

            packages = self._shipengine_compute_packages(picking=picking)

            # Use stored rate_id if available, otherwise get new rates
            rate_id = picking.shipengine_rate_id if hasattr(picking, 'shipengine_rate_id') and picking.shipengine_rate_id else None

            if rate_id:
                # Purchase label from existing rate
                payload = {
                    'rate_id': rate_id,
                    'label_format': self.shipengine_label_format or 'pdf',
                    'label_layout': '4x6',
                }
                label_data = self._shipengine_request('POST', '/v1/labels', payload)
            else:
                # Get rates first, filter out excluded service codes, then pick cheapest
                raw_rates = self._shipengine_get_rates_raw(ship_from, ship_to, packages)
                eligible = self._shipengine_filter_rates(raw_rates, self._shipengine_excluded_set())
                if not eligible:
                    raise UserError(_('No shipping rates available for picking %s.', picking.name))
                cheapest = min(eligible, key=lambda r: float(r.get('shipping_amount', {}).get('amount', 9999)))
                payload = {
                    'rate_id': cheapest['rate_id'],
                    'label_format': self.shipengine_label_format or 'pdf',
                    'label_layout': '4x6',
                }
                label_data = self._shipengine_request('POST', '/v1/labels', payload)

            tracking_number = label_data.get('tracking_number', '')
            label_download = label_data.get('label_download', {})
            label_url = label_download.get('pdf') or label_download.get('png') or label_download.get('href', '')

            # Store label URL on picking for download/print
            if hasattr(picking, 'shipengine_label_url'):
                picking.shipengine_label_url = label_url
            if hasattr(picking, 'shipengine_label_id'):
                picking.shipengine_label_id = label_data.get('label_id', '')

            results.append({
                'exact_price': float(label_data.get('shipment_cost', {}).get('amount', 0)),
                'tracking_number': tracking_number,
            })

            _logger.info(
                'ShipEngine label created for %s: tracking=%s, label=%s',
                picking.name, tracking_number, label_url,
            )

        return results

    def shipengine_get_tracking_link(self, picking):
        """Return tracking URL for a picking."""
        self.ensure_one()
        if picking.carrier_tracking_ref:
            return f'https://track.shipengine.com/{picking.carrier_tracking_ref}'
        return ''

    def shipengine_cancel_shipment(self, pickings):
        """Void a ShipEngine label."""
        self.ensure_one()
        for picking in pickings:
            label_id = picking.shipengine_label_id if hasattr(picking, 'shipengine_label_id') else None
            if label_id:
                try:
                    self._shipengine_request('PUT', f'/v1/labels/{label_id}/void')
                    _logger.info('ShipEngine label %s voided for %s', label_id, picking.name)
                except UserError:
                    _logger.warning('Failed to void ShipEngine label %s', label_id)
