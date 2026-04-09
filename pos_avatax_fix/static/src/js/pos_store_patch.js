/** @odoo-module */

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
    /**
     * Override to allow AvaTax calculation even without a customer.
     * For Take Now orders, tax is based on the POS warehouse location.
     * The backend partner_shipping_id computed field handles the fallback.
     */
    async getAvataxTaxesRpc() {
        if (!this.config.module_pos_avatax) {
            return;
        }

        try {
            const order = this.getOrder();
            if (this.env.services.ui.isBlocked) {
                return;
            }

            // REMOVED: the original `!order.partner_id` guard.
            // We always calculate tax — the backend uses the warehouse
            // address when no customer is set or address is incomplete.

            this.env.services.ui.block({ message: _t("Updating Avatax taxes...") });

            const serialized = order.serializeForORM();
            const data = await this.data.call("pos.order", "get_order_tax_details", [[serialized]]);
            const modelToAdd = {};
            for (const [model, records] of Object.entries(data)) {
                const modelKey = this.data.opts.databaseTable[model]?.key;

                if (!modelKey) {
                    modelToAdd[model] = records;
                    continue;
                }
            }

            this.models.connectNewData(modelToAdd);
        } catch {
            this.dialog.add(AlertDialog, {
                title: _t("Error while loading Avatax taxes"),
                body: _t(
                    "Unable to load Avatax taxes, please verify partner information and Avatax API configuration."
                ),
            });
        } finally {
            this.env.services.ui.unblock();
        }
    },
});
