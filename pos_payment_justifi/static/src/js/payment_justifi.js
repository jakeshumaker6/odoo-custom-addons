/** @odoo-module */

import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";
import { register_payment_method } from "@point_of_sale/app/services/pos_store";
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
    setup(pos, payment_method_id) {
        super.setup(pos, payment_method_id);
        this.pollingInterval = null;
        this.pollingTimeout = null;
    }

    /**
     * Get the pending payment line for JustiFi.
     */
    pendingJustifiLine() {
        return this.pos.getPendingPaymentLine("justifi");
    }

    /**
     * Send a payment request to the JustiFi terminal.
     *
     * @param {string} uuid - The payment line UUID
     * @returns {Promise<boolean>} - True if successful
     */
    async sendPaymentRequest(uuid) {
        super.sendPaymentRequest(uuid);

        const paymentLine = this.pendingJustifiLine();
        if (!paymentLine) {
            console.error("JustiFi: Payment line not found", uuid);
            return false;
        }

        const terminalId = this.payment_method_id.justifi_terminal_id;

        if (!terminalId) {
            this._showError(_t("JustiFi Terminal ID is not configured."));
            return false;
        }

        paymentLine.setPaymentStatus("waitingCard");

        try {
            // Send payment request to backend
            const result = await this.pos.data.silentCall(
                "pos.payment.method",
                "justifi_payment_request",
                [[this.payment_method_id.id]],
                {
                    amount: paymentLine.amount,
                    currency_id: this.pos.currency.id,
                    pos_order_id: this.pos.getOrder().name,
                }
            );

            if (result.error) {
                this._showError(result.error);
                paymentLine.setPaymentStatus("retry");
                return false;
            }

            // Store checkout and terminal info for status polling
            paymentLine.justifi_checkout_id = result.checkout_id;
            paymentLine.justifi_terminal_action_id = result.terminal_action_id;
            paymentLine.justifi_terminal_id = result.terminal_id;

            console.log("JustiFi: Payment sent to terminal", result);

            // Start polling for payment status
            return await this._pollPaymentStatus(paymentLine, uuid);

        } catch (error) {
            console.error("JustiFi: Payment request error", error);
            this._showError(_t("Failed to send payment to terminal. Please try again."));
            paymentLine.setPaymentStatus("retry");
            return false;
        }
    }

    /**
     * Poll for payment status until completed or timeout.
     *
     * @param {Object} paymentLine - The payment line
     * @param {string} uuid - The payment line UUID
     * @returns {Promise<boolean>} - True if payment successful
     */
    async _pollPaymentStatus(paymentLine, uuid) {
        const MAX_POLL_TIME = 95000; // 95 seconds (JustiFi terminal sessions timeout at 90s)
        const POLL_INTERVAL = 2000; // 2 seconds
        const startTime = Date.now();

        return new Promise((resolve) => {
            const pollStatus = async () => {
                // Check if cancelled or user clicked retry
                if (paymentLine.payment_status === "retry" || paymentLine.payment_status === "cancelled") {
                    this._stopPolling();
                    resolve(false);
                    return;
                }

                // Check if Force Done was clicked (status set to "done" externally)
                if (paymentLine.payment_status === "done") {
                    this._stopPolling();
                    resolve(true);
                    return;
                }

                // Check for timeout
                if (Date.now() - startTime > MAX_POLL_TIME) {
                    console.warn("JustiFi: Payment polling timeout");
                    this._stopPolling();
                    paymentLine.setPaymentStatus("force_done");
                    this._showError(_t("Terminal session timed out. If the payment was completed on the terminal, click 'Force Done'. Otherwise, retry."));
                    resolve(false);
                    return;
                }

                try {
                    const status = await this.pos.data.silentCall(
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
                        paymentLine.setPaymentStatus("done");
                        paymentLine.justifi_payment_id = status.payment_id;
                        paymentLine.transaction_id = status.payment_id || status.checkout_id;
                        console.log("JustiFi: Payment successful", status);
                        resolve(true);
                        return;
                    } else if (status.is_failed) {
                        // Payment failed or cancelled on terminal
                        this._stopPolling();
                        paymentLine.setPaymentStatus("retry");
                        this._showError(_t("Payment was declined or cancelled on the terminal."));
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
     * @param {Object} order - The POS order
     * @param {string} uuid - The payment line UUID
     * @returns {Promise<boolean>} - True if cancelled
     */
    async sendPaymentCancel(order, uuid) {
        super.sendPaymentCancel(order, uuid);

        this._stopPolling();

        const paymentLine = this.pendingJustifiLine();

        if (!paymentLine || !paymentLine.justifi_checkout_id) {
            return true;
        }

        try {
            const result = await this.pos.data.silentCall(
                "pos.payment.method",
                "justifi_cancel_payment",
                [],
                {
                    checkout_id: paymentLine.justifi_checkout_id,
                    terminal_id: paymentLine.justifi_terminal_id,
                }
            );

            console.log("JustiFi: Cancel result", result);

            if (result.error) {
                console.warn("JustiFi: Cancel may have failed:", result.error);
            }

            return true;

        } catch (error) {
            console.error("JustiFi: Cancel error", error);
            // Return true anyway — the payment line will be removed
            // and the terminal session will expire on its own
            return true;
        }
    }

    /**
     * Close the payment interface.
     */
    close() {
        this._stopPolling();
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
