/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ShippingRatePopup } from "@pos_shipengine/js/shipping_rate_popup";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { jsonrpc } from "@web/core/network/rpc";

patch(PaymentScreen.prototype, {
    /**
     * Override toggleShippingDatePicker to fetch shipping rates after date selection.
     */
    async toggleShippingDatePicker() {
        const order = this.currentOrder;
        const hadDate = order.getShippingDate();

        // Call original to handle date picker
        await super.toggleShippingDatePicker(...arguments);

        // If a shipping date was just set (not cleared), fetch rates
        if (!hadDate && order.getShippingDate() && this.pos.config.shipengine_carrier_id) {
            await this._fetchAndShowShippingRates();
        }

        // If shipping date was cleared, remove the shipping line
        if (hadDate && !order.getShippingDate()) {
            this._removeShippingLine();
        }
    },

    /**
     * Fetch shipping rates from backend and show the selection popup.
     */
    async _fetchAndShowShippingRates() {
        const order = this.currentOrder;
        const partner = order.getPartner();

        if (!partner) {
            this.notification.add(_t("Please select a customer first."), { type: "warning" });
            return;
        }

        // Build order line data for weight calculation
        const orderLineData = order.get_orderlines()
            .filter(line => !line.is_shipping_charge)
            .map(line => ({
                product_id: line.product_id.id,
                qty: line.get_quantity(),
            }));

        this.notification.add(_t("Fetching shipping rates..."), { type: "info" });

        try {
            const result = await jsonrpc("/pos_shipengine/get_rates", {
                partner_id: partner.id,
                config_id: this.pos.config.id,
                order_line_data: orderLineData,
            });

            if (result.error) {
                this.notification.add(result.error, { type: "danger" });
                // Fall back to custom amount popup
                this._showShippingRatePopup([]);
                return;
            }

            const tiers = result.tiers || [];
            this._showShippingRatePopup(tiers);

        } catch (error) {
            console.error("ShipEngine rate fetch failed:", error);
            this.notification.add(
                _t("Could not fetch shipping rates. You can enter a custom amount."),
                { type: "warning" }
            );
            // Fall back to custom amount popup
            this._showShippingRatePopup([]);
        }
    },

    /**
     * Show the shipping rate selection popup.
     */
    _showShippingRatePopup(tiers) {
        this.dialog.add(ShippingRatePopup, {
            tiers: tiers,
            getPayload: (selectedRate) => {
                this._applyShippingRate(selectedRate);
            },
        });
    },

    /**
     * Apply the selected shipping rate to the order.
     * Adds/updates a shipping line item on the order.
     */
    _applyShippingRate(rate) {
        const order = this.currentOrder;

        // Remove existing shipping line if any
        this._removeShippingLine();

        // Store shipping metadata on the order
        order.shipping_tier = rate.tier;
        order.shipping_amount = rate.amount;
        order.shipping_carrier_name = rate.carrier_name || '';
        order.shipping_service_code = rate.service_code || '';
        order.shipping_rate_id = rate.rate_id || '';

        // Find the shipping product from the POS loaded products
        // We look for a product named "ShipEngine Shipping" or use a fallback
        const shippingProduct = this._getShippingProduct();

        if (shippingProduct && rate.amount > 0) {
            // Add shipping as an order line
            const line = order.addProduct(shippingProduct, {
                price: rate.amount,
                quantity: 1,
                merge: false,
                extras: { is_shipping_charge: true },
            });
            if (line) {
                line.is_shipping_charge = true;
                line.set_unit_price(rate.amount);
                // Prevent cashier from modifying the shipping line manually
                line.price_type = "automatic";
            }
        }

        const tierLabel = {
            express: _t("Express"),
            standard: _t("Standard"),
            economy: _t("Economy"),
            custom: _t("Custom"),
        }[rate.tier] || rate.tier;

        this.notification.add(
            _t("Shipping: %s — %s", tierLabel, `$${rate.amount.toFixed(2)}`),
            { type: "success" }
        );
    },

    /**
     * Remove the shipping charge line from the order.
     */
    _removeShippingLine() {
        const order = this.currentOrder;
        const shippingLines = order.get_orderlines().filter(
            line => line.is_shipping_charge
        );
        for (const line of shippingLines) {
            order.removeOrderline(line);
        }
        order.shipping_tier = false;
        order.shipping_amount = 0;
        order.shipping_carrier_name = '';
        order.shipping_service_code = '';
        order.shipping_rate_id = '';
    },

    /**
     * Get the shipping product from POS loaded products.
     */
    _getShippingProduct() {
        // Try to find the ShipEngine delivery product
        const products = this.pos.models["product.product"].getAll();
        let shippingProduct = products.find(
            p => p.default_code === 'SHIPENGINE_SHIPPING' || p.display_name === 'ShipEngine Shipping'
        );

        // Fallback: find any delivery/shipping product
        if (!shippingProduct) {
            shippingProduct = products.find(
                p => p.display_name && p.display_name.toLowerCase().includes('shipping')
            );
        }

        return shippingProduct || null;
    },
});
