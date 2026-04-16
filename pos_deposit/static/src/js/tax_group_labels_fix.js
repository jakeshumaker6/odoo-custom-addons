/** @odoo-module */

import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { patch } from "@web/core/utils/patch";

/**
 * Fix: TypeError on pos.order.line getters when order_id is undefined.
 *
 * During the reactive model's create flow for pos.order.line, there is a window
 * where order_id has not yet been connected (it's in dataToConnect, not rawData).
 * Multiple core getters access this.order_id.* without null guards, which crashes
 * when lazy getter computation or triggerRecomputeAllPrices fires during line creation.
 *
 * This patch adds guards to all affected getters.
 */
patch(PosOrderline.prototype, {
    get currency() {
        if (!this.order_id) {
            return this.models["res.currency"].getFirst();
        }
        return this.order_id.currency;
    },

    get prices() {
        if (!this.order_id) {
            return { total_included: 0, total_excluded: 0, taxes_data: [] };
        }
        const data = this.order_id.prices.baseLineByLineUuids[this.uuid];
        return data.tax_details;
    },

    get unitPrices() {
        if (!this.order_id) {
            return { total_included: 0, total_excluded: 0, taxes_data: [] };
        }
        const data = this.order_id.unitPrices.baseLineByLineUuids[this.uuid];
        return data.tax_details;
    },

    get priceIncl() {
        if (!this.order_id) {
            return 0;
        }
        return this.currency.round(this.prices.total_included * this.order_id.orderSign);
    },

    get priceExcl() {
        if (!this.order_id) {
            return 0;
        }
        return this.currency.round(this.prices.total_excluded * this.order_id.orderSign);
    },

    get priceInclNoDiscount() {
        if (!this.order_id) {
            return 0;
        }
        return this.currency.round(
            this.prices.no_discount_total_included * this.order_id.orderSign
        );
    },

    get priceExclNoDiscount() {
        if (!this.order_id) {
            return 0;
        }
        return this.currency.round(
            this.prices.no_discount_total_excluded * this.order_id.orderSign
        );
    },

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
