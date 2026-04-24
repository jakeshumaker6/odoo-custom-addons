"""Unit tests for the ShipEngine delivery carrier integration.

Run on an Odoo.sh staging branch with:
    odoo-bin -d <staging_db> -i delivery_shipengine \
        --test-enable --test-tags=delivery_shipengine --stop-after-init
"""
import types
from unittest.mock import MagicMock, patch

import requests

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


def _fake_rate(service_code, amount, days, carrier="USPS", service_type=None, rate_id=None):
    return {
        "carrier_friendly_name": carrier,
        "service_type": service_type or service_code,
        "service_code": service_code,
        "rate_id": rate_id or "r-" + service_code,
        "shipping_amount": {"amount": amount},
        "delivery_days": days,
    }


def _mock_rates_response(rates):
    """Return a side_effect suitable for patching requests.request to emit /v1/rates data."""
    def _side_effect(method, url, json=None, headers=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"rate_response": {"rates": rates, "errors": []}}
        return resp
    return _side_effect


@tagged("post_install", "-at_install", "-standard", "delivery_shipengine")
class TestShipEngineCarrier(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Carrier = cls.env["delivery.carrier"]
        cls.Partner = cls.env["res.partner"]
        cls.US = cls.env["res.country"].search([("code", "=", "US")], limit=1)
        cls.MN = cls.env["res.country.state"].search(
            [("country_id", "=", cls.US.id), ("code", "=", "MN")], limit=1,
        )

        cls.product = cls.env.ref("delivery_shipengine.product_product_shipengine")
        cls.carrier = cls.Carrier.create({
            "name": "Test ShipEngine",
            "delivery_type": "shipengine",
            "product_id": cls.product.id,
            "integration_level": "rate_and_ship",
            "shipengine_api_key": "fake-api-key",
            "shipengine_default_weight_oz": 16.0,
            "shipengine_default_package_code": "package",
            "shipengine_label_format": "pdf",
            "shipengine_excluded_service_codes": "usps_media_mail,usps_library_mail",
        })

        cls.destination = cls.Partner.create({
            "name": "Test Customer",
            "street": "123 Main St",
            "city": "Minneapolis",
            "state_id": cls.MN.id,
            "zip": "55401",
            "country_id": cls.US.id,
            "phone": "555-000-0000",
        })

    # ─── Bug #1: partner.mobile gone in Odoo 19 ──────────────────────────

    def test_format_address_partner_without_mobile_attr(self):
        """A res.partner with no phone must not AttributeError on missing .mobile."""
        p = self.Partner.create({
            "name": "No Phone",
            "street": "1 Main",
            "city": "Mpls",
            "state_id": self.MN.id,
            "zip": "55401",
            "country_id": self.US.id,
        })
        addr = self.carrier._shipengine_format_address(p)
        self.assertEqual(addr["phone"], "0000000000")
        self.assertEqual(addr["country_code"], "US")
        self.assertEqual(addr["state_province"], "MN")

    def test_format_address_uses_phone_when_present(self):
        addr = self.carrier._shipengine_format_address(self.destination)
        self.assertEqual(addr["phone"], "555-000-0000")

    # ─── Bug #2: blacklist filtering ─────────────────────────────────────

    def test_excluded_set_parses_config(self):
        self.assertEqual(
            self.carrier._shipengine_excluded_set(),
            {"usps_media_mail", "usps_library_mail"},
        )

    def test_tiering_skips_excluded_service_codes(self):
        rates = [
            _fake_rate("usps_media_mail", 5.22, 5),
            _fake_rate("usps_ground_advantage", 9.50, 6),
            _fake_rate("ups_ground", 12.00, 4),
        ]
        tiers = self.carrier._shipengine_group_rates_into_tiers(
            rates, excluded_service_codes=["usps_media_mail"],
        )
        codes = [t["service_code"] for t in tiers]
        self.assertNotIn("usps_media_mail", codes)
        by_tier = {t["tier"]: t for t in tiers}
        self.assertEqual(by_tier["standard"]["service_code"], "usps_ground_advantage")

    def test_tiering_keeps_all_when_no_exclusion(self):
        rates = [_fake_rate("usps_media_mail", 5.22, 5)]
        tiers = self.carrier._shipengine_group_rates_into_tiers(rates)
        self.assertEqual(tiers[0]["service_code"], "usps_media_mail")

    def test_filter_rates_helper(self):
        rates = [
            _fake_rate("a", 1.0, 3),
            _fake_rate("b", 2.0, 3),
            _fake_rate("c", 3.0, 3),
        ]
        self.assertEqual(len(self.carrier._shipengine_filter_rates(rates, ["b"])), 2)
        self.assertEqual(len(self.carrier._shipengine_filter_rates(rates, None)), 3)

    # ─── Bug #3: dispatch respects the blacklist ────────────────────────

    def test_rate_shipment_ignores_cheaper_excluded_service(self):
        """Media Mail at $5.22 is cheapest, but must not be chosen."""
        rates = [
            _fake_rate("usps_media_mail", 5.22, 5),
            _fake_rate("usps_ground_advantage", 9.50, 6),
            _fake_rate("ups_ground", 12.00, 4),
        ]
        order = types.SimpleNamespace(
            partner_id=self.destination,
            partner_shipping_id=self.destination,
            order_line=[],
        )
        target = "odoo.addons.delivery_shipengine.models.delivery_carrier.requests.request"
        with patch(target, side_effect=_mock_rates_response(rates)):
            res = self.carrier.shipengine_rate_shipment(order)
        self.assertTrue(res["success"])
        # Cheapest non-excluded is usps_ground_advantage @ 9.50
        self.assertEqual(res["price"], 9.50)

    def test_rate_shipment_handles_no_rates(self):
        order = types.SimpleNamespace(
            partner_id=self.destination,
            partner_shipping_id=self.destination,
            order_line=[],
        )
        target = "odoo.addons.delivery_shipengine.models.delivery_carrier.requests.request"
        with patch(target, side_effect=_mock_rates_response([])):
            res = self.carrier.shipengine_rate_shipment(order)
        self.assertFalse(res["success"])
        self.assertEqual(res["price"], 0.0)
        self.assertIn("No shipping rates", res["error_message"])

    def test_rate_shipment_handles_api_error(self):
        def boom(*a, **kw):
            err = requests.exceptions.HTTPError("401")
            err.response = MagicMock()
            err.response.json.return_value = {"errors": [{"message": "Unauthorized"}]}
            raise err

        order = types.SimpleNamespace(
            partner_id=self.destination,
            partner_shipping_id=self.destination,
            order_line=[],
        )
        target = "odoo.addons.delivery_shipengine.models.delivery_carrier.requests.request"
        with patch(target, side_effect=boom):
            res = self.carrier.shipengine_rate_shipment(order)
        self.assertFalse(res["success"])
        self.assertIn("Unauthorized", res["error_message"])

    # ─── Weight & package computation ───────────────────────────────────

    def test_compute_packages_defaults_to_one_oz_when_empty(self):
        pkgs = self.carrier._shipengine_compute_packages()
        self.assertEqual(pkgs[0]["weight"]["value"], 1.0)
        self.assertEqual(pkgs[0]["weight"]["unit"], "ounce")
        self.assertEqual(pkgs[0]["package_code"], "package")

    def test_compute_packages_converts_kg_to_oz(self):
        line = types.SimpleNamespace(
            product_id=types.SimpleNamespace(weight=2.0, type="consu"),
            product_qty=3, product_uom_qty=3,
            is_delivery=False, display_type=False,
        )
        pkgs = self.carrier._shipengine_compute_packages(order_lines=[line])
        # 2 kg * 35.274 oz/kg * 3 qty = 211.6
        self.assertAlmostEqual(pkgs[0]["weight"]["value"], 211.6, places=1)

    def test_compute_packages_skips_delivery_line(self):
        """The delivery line is a service and must not double-contribute weight."""
        product_line = types.SimpleNamespace(
            product_id=types.SimpleNamespace(weight=1.0, type="consu"),
            product_qty=1, product_uom_qty=1,
            is_delivery=False, display_type=False,
        )
        delivery_line = types.SimpleNamespace(
            product_id=types.SimpleNamespace(weight=0.0, type="service"),
            product_qty=1, product_uom_qty=1,
            is_delivery=True, display_type=False,
        )
        pkgs = self.carrier._shipengine_compute_packages(order_lines=[product_line, delivery_line])
        # Only the 1 kg consumable should contribute: 1 * 35.274 = 35.3 oz
        self.assertAlmostEqual(pkgs[0]["weight"]["value"], 35.3, places=1)

    def test_compute_packages_skips_service_products(self):
        service_line = types.SimpleNamespace(
            product_id=types.SimpleNamespace(weight=0.0, type="service"),
            product_qty=5, product_uom_qty=5,
            is_delivery=False, display_type=False,
        )
        pkgs = self.carrier._shipengine_compute_packages(order_lines=[service_line])
        # No consumable lines → min 1 oz
        self.assertEqual(pkgs[0]["weight"]["value"], 1.0)

    def test_compute_packages_skips_display_type_lines(self):
        section_line = types.SimpleNamespace(
            product_id=types.SimpleNamespace(weight=0.0, type="consu"),
            product_qty=1, product_uom_qty=1,
            is_delivery=False, display_type="line_section",
        )
        pkgs = self.carrier._shipengine_compute_packages(order_lines=[section_line])
        self.assertEqual(pkgs[0]["weight"]["value"], 1.0)

    def test_compute_packages_honors_wizard_order_weight_context(self):
        """When the Add Shipping wizard types a weight, that value wins."""
        line = types.SimpleNamespace(
            product_id=types.SimpleNamespace(weight=1.0, type="consu"),
            product_qty=1, product_uom_qty=1,
            is_delivery=False, display_type=False,
        )
        # With kg UoM: 5 kg override → 5 * 35.274 = 176.4 oz
        pkgs = self.carrier.with_context(order_weight=5.0)._shipengine_compute_packages(
            order_lines=[line],
        )
        to_oz = self.carrier._shipengine_weight_unit_to_oz_factor()
        self.assertAlmostEqual(pkgs[0]["weight"]["value"], 5.0 * to_oz, places=1)

    def test_compute_packages_zero_context_weight_falls_through(self):
        """order_weight=0 should not override — fall through to line-based calc."""
        line = types.SimpleNamespace(
            product_id=types.SimpleNamespace(weight=2.0, type="consu"),
            product_qty=3, product_uom_qty=3,
            is_delivery=False, display_type=False,
        )
        to_oz = self.carrier._shipengine_weight_unit_to_oz_factor()
        pkgs = self.carrier.with_context(order_weight=0.0)._shipengine_compute_packages(
            order_lines=[line],
        )
        self.assertAlmostEqual(pkgs[0]["weight"]["value"], 2.0 * to_oz * 3, places=1)

    def test_weight_unit_factor_returns_known_value(self):
        """Factor must be 16 (lb) or 35.274 (kg)."""
        factor = self.carrier._shipengine_weight_unit_to_oz_factor()
        self.assertIn(factor, (16.0, 35.274))

    def test_compute_packages_falls_back_to_default_weight(self):
        line = types.SimpleNamespace(
            product_id=types.SimpleNamespace(weight=0.0, type="consu"),
            product_qty=2, product_uom_qty=2,
            is_delivery=False, display_type=False,
        )
        pkgs = self.carrier._shipengine_compute_packages(order_lines=[line])
        # 16 oz default * 2 qty = 32
        self.assertEqual(pkgs[0]["weight"]["value"], 32.0)

    # ─── get_all_rates wrapper ──────────────────────────────────────────

    def test_get_all_rates_reports_excluded_count(self):
        rates = [
            _fake_rate("usps_media_mail", 5.22, 5),
            _fake_rate("usps_ground_advantage", 9.50, 6),
        ]
        target = "odoo.addons.delivery_shipengine.models.delivery_carrier.requests.request"
        with patch(target, side_effect=_mock_rates_response(rates)):
            result = self.carrier.shipengine_get_all_rates(self.destination)
        self.assertEqual(result["raw_rate_count"], 2)
        self.assertEqual(result["excluded_count"], 1)
        codes = [t["service_code"] for t in result["tiers"]]
        self.assertNotIn("usps_media_mail", codes)

    def test_get_all_rates_requires_warehouse(self):
        # Create a carrier tied to a company whose warehouse has no partner
        Company = self.env["res.company"]
        alt_company = Company.create({"name": "Orphan Co"})
        # Remove the warehouse partner
        wh = self.env["stock.warehouse"].search([("company_id", "=", alt_company.id)], limit=1)
        if wh:
            wh.partner_id = False
        orphan_carrier = self.carrier.copy({"company_id": alt_company.id})
        with self.assertRaises(UserError):
            orphan_carrier.shipengine_get_all_rates(self.destination)
