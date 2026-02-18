/** @odoo-module */

import { PaymentInterface } from "@point_of_sale/app/payment/payment_interface";
import { register_payment_method } from "@point_of_sale/app/payment/payment_method_registry";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

/**
 * JustiFi Terminal Payment Interface
 *
 * Handles card-present payments via JustiFi terminals (Verifone E285).
 */
export class PaymentJustifi extends PaymentInterface {
    /**
     * Setup the payment interface
     */
    setup() {
        super.setup(...arguments);
        this.pollingInterval = null;
        this.pollingTimeout = null;
    }

    /**
     * Send a payment request to the JustiFi terminal.
     *
     * @param {string} cid - The payment line client ID
     * @returns {Promise<boolean>} - True if successful
     */
    async send_payment_request(cid) {
        await super.send_payment_request(...arguments);

        const paymentLine = this.pos.getPendingPaymentLine(cid);
        if (!paymentLine) {
            console.error("JustiFi: Payment line not found", cid);
            return false;
        }

        const paymentMethod = paymentLine.payment_method_id;
        const terminalId = paymentMethod.justifi_terminal_id;

        if (!terminalId) {
            this._showError(_t("JustiFi Terminal ID is not configured."));
            return false;
        }

        paymentLine.set_payment_status("waitingCard");

        try {
            // Send payment request to backend
            const result = await this.env.services.orm.silent.call(
                "pos.payment.method",
                "justifi_payment_request",
                [[paymentMethod.id]],
                {
                    amount: paymentLine.amount,
                    currency_id: this.pos.currency.id,
                    pos_order_id: this.pos.get_order().name,
                }
            );

            if (result.error) {
                this._showError(result.error);
                paymentLine.set_payment_status("retry");
                return false;
            }

            // Store checkout and terminal info for status polling
            paymentLine.justifi_checkout_id = result.checkout_id;
            paymentLine.justifi_terminal_action_id = result.terminal_action_id;
            paymentLine.justifi_terminal_id = result.terminal_id;

            console.log("JustiFi: Payment sent to terminal", result);

            // Start polling for payment status
            return await this._pollPaymentStatus(paymentLine, cid);

        } catch (error) {
            console.error("JustiFi: Payment request error", error);
            this._showError(_t("Failed to send payment to terminal. Please try again."));
            paymentLine.set_payment_status("retry");
            return false;
        }
    }

    /**
     * Poll for payment status until completed or timeout.
     *
     * @param {Object} paymentLine - The payment line
     * @param {string} cid - The payment line client ID
     * @returns {Promise<boolean>} - True if payment successful
     */
    async _pollPaymentStatus(paymentLine, cid) {
        const MAX_POLL_TIME = 120000; // 2 minutes
        const POLL_INTERVAL = 2000; // 2 seconds
        const startTime = Date.now();

        return new Promise((resolve) => {
            const pollStatus = async () => {
                // Check if cancelled
                if (paymentLine.payment_status === "retry" || paymentLine.payment_status === "cancelled") {
                    this._stopPolling();
                    resolve(false);
                    return;
                }

                // Check for timeout
                if (Date.now() - startTime > MAX_POLL_TIME) {
                    console.warn("JustiFi: Payment polling timeout");
                    this._stopPolling();
                    paymentLine.set_payment_status("timeout");
                    this._showError(_t("Payment timeout. Please check the terminal."));
                    resolve(false);
                    return;
                }

                try {
                    const status = await this.env.services.orm.silent.call(
                        "pos.payment.method",
                        "justifi_payment_status",
                        [],
                        {
                            checkout_id: paymentLine.justifi_checkout_id,
                            terminal_action_id: paymentLine.justifi_terminal_action_id,
                        }
                    );

                    console.log("JustiFi: Status poll result", status);

                    if (status.error) {
                        console.warn("JustiFi: Status check error", status.error);
                        // Continue polling on transient errors
                    } else if (status.is_paid) {
                        // Payment successful
                        this._stopPolling();
                        paymentLine.set_payment_status("done");
                        paymentLine.justifi_payment_id = status.payment_id;
                        paymentLine.transaction_id = status.payment_id || status.checkout_id;
                        console.log("JustiFi: Payment successful", status);
                        resolve(true);
                        return;
                    } else if (status.is_failed) {
                        // Payment failed
                        this._stopPolling();
                        paymentLine.set_payment_status("retry");
                        this._showError(_t("Payment was declined or cancelled."));
                        resolve(false);
                        return;
                    }
                    // Continue polling if pending

                } catch (error) {
                    console.error("JustiFi: Status poll error", error);
                    // Continue polling on network errors
                }

                // Schedule next poll
                this.pollingTimeout = setTimeout(pollStatus, POLL_INTERVAL);
            };

            // Start polling
            pollStatus();
        });
    }

    /**
     * Stop the polling loop.
     */
    _stopPolling() {
        if (this.pollingTimeout) {
            clearTimeout(this.pollingTimeout);
            this.pollingTimeout = null;
        }
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }

    /**
     * Cancel the current payment request.
     *
     * @param {boolean} force - Force cancel
     * @param {string} cid - The payment line client ID
     * @returns {Promise<boolean>} - True if cancelled
     */
    async send_payment_cancel(force = false, cid = null) {
        await super.send_payment_cancel(...arguments);

        this._stopPolling();

        const paymentLine = cid ? this.pos.getPendingPaymentLine(cid) : this.pos.get_order()?.selected_paymentline;

        if (!paymentLine || !paymentLine.justifi_checkout_id) {
            return true;
        }

        try {
            const result = await this.env.services.orm.silent.call(
                "pos.payment.method",
                "justifi_cancel_payment",
                [],
                {
                    checkout_id: paymentLine.justifi_checkout_id,
                    terminal_id: paymentLine.justifi_terminal_id,
                }
            );

            console.log("JustiFi: Cancel result", result);

            paymentLine.set_payment_status("cancelled");
            return true;

        } catch (error) {
            console.error("JustiFi: Cancel error", error);
            // Still mark as cancelled locally
            paymentLine.set_payment_status("retry");
            return true;
        }
    }

    /**
     * Close the payment interface.
     */
    close() {
        this._stopPolling();
        super.close();
    }

    /**
     * Show an error dialog.
     *
     * @param {string} message - Error message
     */
    _showError(message) {
        this.env.services.dialog.add(AlertDialog, {
            title: _t("JustiFi Terminal Error"),
            body: message,
        });
    }
}

// Register the payment method
register_payment_method("justifi", PaymentJustifi);
