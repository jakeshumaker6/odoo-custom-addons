/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosPaymentProviderCards } from "@point_of_sale/backend/pos_payment_provider_cards/pos_payment_provider_cards";
import { onWillStart } from "@odoo/owl";

/**
 * Patch the PosPaymentProviderCards component to add JustiFi as a provider option.
 *
 * This patches the setup method to inject JustiFi into the providers list
 * after the original providers are loaded.
 */
patch(PosPaymentProviderCards.prototype, {
    setup() {
        super.setup();

        // Store reference to original state for patching
        const originalState = this.state;

        onWillStart(async () => {
            // After the original onWillStart runs, add JustiFi if module is available
            // Check if JustiFi module is installed
            const justifiModule = await this.orm.call("ir.module.module", "search_read", [
                [["name", "=", "pos_payment_justifi"], ["state", "=", "installed"]],
                ["id", "name", "state"],
            ]);

            if (justifiModule.length > 0) {
                // Add JustiFi to the providers list
                const justifiProvider = {
                    selection: "justifi",
                    provider: "JustiFi",
                    id: justifiModule[0].id,
                    name: "pos_payment_justifi",
                    state: "installed",
                };

                // Check if JustiFi is already in the list
                const exists = originalState.providers.some(p => p.selection === "justifi");
                if (!exists) {
                    originalState.providers.push(justifiProvider);
                }
            }
        });
    },
});
