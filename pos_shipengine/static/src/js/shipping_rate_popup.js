/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";

/**
 * Shipping Rate Selection Popup for POS Ship Later flow.
 *
 * Displays tiered shipping options (Express / Standard / Economy) from ShipEngine
 * plus a custom amount input for manual overrides.
 */
export class ShippingRatePopup extends Component {
    static template = "pos_shipengine.ShippingRatePopup";
    static components = { Dialog };
    static props = {
        tiers: { type: Array },
        close: Function,
        getPayload: Function,
        title: { type: String, optional: true },
    };
    static defaultProps = {
        title: _t("Select Shipping Option"),
    };

    setup() {
        this.state = useState({
            selectedTier: null,
            customAmount: "",
            useCustom: false,
        });
        useHotkey("escape", () => this.props.close());
    }

    get tierLabels() {
        return {
            express: _t("Express"),
            standard: _t("Standard"),
            economy: _t("Economy"),
        };
    }

    selectTier(tier) {
        this.state.selectedTier = tier;
        this.state.useCustom = false;
    }

    selectCustom() {
        this.state.selectedTier = null;
        this.state.useCustom = true;
    }

    get canConfirm() {
        if (this.state.useCustom) {
            const amt = parseFloat(this.state.customAmount);
            return !isNaN(amt) && amt >= 0;
        }
        return this.state.selectedTier !== null;
    }

    confirm() {
        if (!this.canConfirm) return;

        let payload;
        if (this.state.useCustom) {
            payload = {
                tier: "custom",
                amount: parseFloat(this.state.customAmount),
                carrier_name: "Custom Shipping",
                service_type: "",
                service_code: "",
                rate_id: "",
                delivery_days: 0,
            };
        } else {
            payload = { ...this.state.selectedTier };
        }

        this.props.getPayload(payload);
        this.props.close();
    }

    formatCurrency(amount) {
        return `$${parseFloat(amount).toFixed(2)}`;
    }
}
