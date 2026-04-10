/** @odoo-module */

import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { DepositRedeemPopup } from "@pos_deposit/js/deposit_redeem_popup";

const DEPOSIT_AMOUNT = 500.00;
const DEPOSIT_PRODUCT_CODE = "DEPOSIT500";

patch(ControlButtons.prototype, {
    /**
     * Collect a $500 deposit from the customer.
     */
    async clickCollectDeposit() {
        const order = this.pos.getOrder();

        // Require customer selection
        if (!order.getPartner()) {
            await this.pos.selectPartner();
            if (!order.getPartner()) {
                this.notification.add(
                    _t("A customer must be selected to collect a deposit."),
                    { type: "warning" },
                );
                return;
            }
        }

        // Find the deposit product
        const depositProduct = this._getDepositProduct();
        if (!depositProduct) {
            this.notification.add(
                _t("Deposit product (DEPOSIT500) not found. Please contact your administrator."),
                { type: "danger" },
            );
            return;
        }

        // Clear any existing lines and add deposit
        const lines = [...(order.lines || [])];
        for (const line of lines) {
            order.removeOrderline(line);
        }

        // Add deposit product via Odoo 19 API
        await this.pos.addLineToCurrentOrder(
            {
                product_tmpl_id: depositProduct.product_tmpl_id,
                price_unit: DEPOSIT_AMOUNT,
                qty: 1,
            },
            { merge: false }
        );

        // Mark order as a deposit
        order.is_deposit = true;

        this.notification.add(
            _t("$500 deposit added for %s", order.getPartner().name),
            { type: "success" },
        );

        // Navigate to payment screen
        this.pos.navigate("PaymentScreen");
    },

    /**
     * Redeem an existing deposit against the current order.
     */
    async clickRedeemDeposit() {
        const order = this.pos.getOrder();

        // Require customer selection
        if (!order.getPartner()) {
            await this.pos.selectPartner();
            if (!order.getPartner()) {
                this.notification.add(
                    _t("A customer must be selected to redeem a deposit."),
                    { type: "warning" },
                );
                return;
            }
        }

        const partner = order.getPartner();

        // Fetch active deposits for this customer
        const deposits = await this.pos.data.call(
            "pos.order",
            "get_active_deposits",
            [partner.id],
        );

        if (!deposits || deposits.length === 0) {
            this.notification.add(
                _t("No active deposits found for %s.", partner.name),
                { type: "warning" },
            );
            return;
        }

        // Show redemption popup
        this.env.services.dialog.add(DepositRedeemPopup, {
            deposits: deposits,
            getPayload: (selectedDeposit) => {
                this._applyDepositRedemption(selectedDeposit);
            },
        });
    },

    /**
     * Apply a deposit redemption as a negative line on the current order.
     */
    async _applyDepositRedemption(deposit) {
        const order = this.pos.getOrder();
        const depositProduct = this._getDepositProduct();

        if (!depositProduct) {
            this.notification.add(
                _t("Deposit product not found."),
                { type: "danger" },
            );
            return;
        }

        // Add negative deposit line (full $500 consumed — forfeit remainder)
        await this.pos.addLineToCurrentOrder(
            {
                product_tmpl_id: depositProduct.product_tmpl_id,
                price_unit: DEPOSIT_AMOUNT,
                qty: -1,
            },
            { merge: false }
        );

        // Store the deposit origin for backend linking
        order.deposit_origin_order_id = deposit.id;

        this.notification.add(
            _t("Deposit %s ($500) applied to order.", deposit.deposit_reference),
            { type: "success" },
        );
    },

    /**
     * Find the DEPOSIT500 product in POS loaded products.
     */
    _getDepositProduct() {
        // Try by default_code on product.product
        let product = this.pos.models["product.product"].getBy(
            "default_code", DEPOSIT_PRODUCT_CODE
        );

        // Fallback: search all products
        if (!product) {
            const all = this.pos.models["product.product"].getAll();
            product = all.find(p => p.default_code === DEPOSIT_PRODUCT_CODE);
        }

        // Fallback: search by name on product.template
        if (!product) {
            const templates = this.pos.models["product.template"].getAll();
            const tmpl = templates.find(t => t.default_code === DEPOSIT_PRODUCT_CODE);
            if (tmpl && tmpl.product_variant_ids && tmpl.product_variant_ids.length > 0) {
                product = tmpl.product_variant_ids[0];
            }
        }

        if (!product) {
            console.error("DEPOSIT500 not found. Available products:",
                this.pos.models["product.product"].getAll().map(
                    p => ({id: p.id, code: p.default_code, name: p.display_name})
                ).slice(0, 10)
            );
        }

        return product || null;
    },
});
