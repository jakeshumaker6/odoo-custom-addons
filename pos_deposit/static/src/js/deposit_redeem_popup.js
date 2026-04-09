/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";

/**
 * Popup showing customer's active deposits for redemption.
 */
export class DepositRedeemPopup extends Component {
    static template = "pos_deposit.DepositRedeemPopup";
    static components = { Dialog };
    static props = {
        deposits: { type: Array },
        close: Function,
        getPayload: Function,
        title: { type: String, optional: true },
    };
    static defaultProps = {
        title: _t("Redeem Deposit"),
    };

    setup() {
        this.state = useState({
            selectedDeposit: null,
        });
        useHotkey("escape", () => this.props.close());
    }

    selectDeposit(deposit) {
        this.state.selectedDeposit = deposit;
    }

    confirm() {
        if (!this.state.selectedDeposit) return;
        this.props.getPayload(this.state.selectedDeposit);
        this.props.close();
    }
}
