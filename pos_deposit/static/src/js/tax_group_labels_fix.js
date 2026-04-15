/** @odoo-module */

import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { patch } from "@web/core/utils/patch";

/**
 * Fix: TypeError: Cannot read properties of undefined (reading 'fiscal_position_id')
 *
 * During the reactive model's create flow for pos.order.line, there is a window
 * where order_id has not yet been connected (it's in dataToConnect, not rawData).
 * The core taxGroupLabels getter accesses this.order_id.fiscal_position_id without
 * a null guard, which crashes when triggerRecomputeAllPrices fires during line creation.
 *
 * This patch adds optional chaining to prevent the crash.
 */
patch(PosOrderline.prototype, {
    get taxGroupLabels() {
        if (!this.order_id) {
            return "";
        }
        let taxes_id = this.tax_ids;
        if (this.order_id.fiscal_position_id) {
            taxes_id = this.order_id.fiscal_position_id.getTaxesAfterFiscalPosition(this.tax_ids);
        }
        return [
            ...new Set(
                taxes_id?.map((tax) => tax.tax_group_id?.pos_receipt_label).filter((label) => label)
            ),
        ].join(" ");
    },
});
