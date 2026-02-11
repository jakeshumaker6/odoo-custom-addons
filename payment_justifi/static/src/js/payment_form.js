/** @odoo-module **/

/**
 * JustiFi Payment Form Handler
 *
 * Initializes and manages the JustiFi modular checkout component
 * for processing card payments in Odoo.
 */

import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";

publicWidget.registry.JustiFiPaymentForm = publicWidget.Widget.extend({
    selector: '#justifi-payment-container',

    /**
     * @override
     */
    start: function () {
        this._super.apply(this, arguments);
        this._initJustiFi();
        return Promise.resolve();
    },

    /**
     * Initialize JustiFi modular checkout component
     */
    _initJustiFi: function () {
        const container = this.el;
        const checkoutId = container.dataset.checkoutId;
        const authToken = container.dataset.authToken;
        const accountId = container.dataset.accountId;
        const paymentMethodGroupId = container.dataset.paymentMethodGroupId;
        const apiUrl = container.dataset.apiUrl;
        const reference = container.dataset.reference;

        console.log('JustiFi: Initializing payment form');
        console.log('JustiFi: checkout_id =', checkoutId);
        console.log('JustiFi: account_id =', accountId);

        if (!checkoutId || !authToken) {
            this._showError('Payment form not properly initialized. Please refresh the page.');
            return;
        }

        // Store for later use
        this.checkoutId = checkoutId;
        this.authToken = authToken;
        this.accountId = accountId;
        this.apiUrl = apiUrl;
        this.reference = reference;

        // Wait for JustiFi web components to be defined
        this._waitForJustiFiComponents().then(() => {
            this._createCheckoutComponent();
        }).catch((error) => {
            console.error('JustiFi: Failed to load web components:', error);
            this._showError('Failed to load payment form. Please refresh the page.');
        });
    },

    /**
     * Wait for JustiFi web components to be available
     */
    _waitForJustiFiComponents: function () {
        return new Promise((resolve, reject) => {
            let attempts = 0;
            const maxAttempts = 50; // 5 seconds total

            const check = () => {
                if (customElements.get('justifi-modular-checkout')) {
                    resolve();
                } else if (attempts >= maxAttempts) {
                    reject(new Error('JustiFi components not loaded'));
                } else {
                    attempts++;
                    setTimeout(check, 100);
                }
            };

            check();
        });
    },

    /**
     * Create and configure the JustiFi checkout component
     */
    _createCheckoutComponent: function () {
        const wrapper = this.el.querySelector('#justifi-component-wrapper');
        const loading = this.el.querySelector('#justifi-loading');

        if (!wrapper) {
            console.error('JustiFi: Component wrapper not found');
            return;
        }

        // Clear any existing content
        wrapper.innerHTML = '';

        // Create modular checkout component
        const checkout = document.createElement('justifi-modular-checkout');
        checkout.setAttribute('auth-token', this.authToken);
        checkout.setAttribute('checkout-id', this.checkoutId);

        // Set account-id - REQUIRED for tokenization
        if (this.accountId) {
            checkout.setAttribute('account-id', this.accountId);
            console.log('JustiFi: Set account-id:', this.accountId);
        }

        // Add card form with simple billing
        const cardForm = document.createElement('justifi-card-form');
        const billingForm = document.createElement('justifi-card-billing-form-simple');

        checkout.appendChild(cardForm);
        checkout.appendChild(billingForm);

        // Add event listeners
        checkout.addEventListener('submit-event', (e) => {
            console.log('JustiFi: submit-event received', e.detail);
            this._handleSubmitEvent(e.detail);
        });

        checkout.addEventListener('error-event', (e) => {
            console.error('JustiFi: error-event received', e.detail);
            this._handleErrorEvent(e.detail);
        });

        checkout.addEventListener('ready', () => {
            console.log('JustiFi: Checkout component ready');
        });

        // Store reference to component
        this.modularCheckout = checkout;

        // Append to DOM
        wrapper.appendChild(checkout);

        // Hide loading, show component
        if (loading) loading.style.display = 'none';
        wrapper.style.display = 'block';

        console.log('JustiFi: Payment form initialized');
    },

    /**
     * Handle successful payment submission
     */
    _handleSubmitEvent: function (detail) {
        console.log('JustiFi: Processing submit event');
        console.log('JustiFi: Detail:', JSON.stringify(detail, null, 2));

        let paymentId = null;

        // Extract payment ID from various possible locations
        if (detail) {
            if (detail.checkout && detail.checkout.successful_payment_id) {
                paymentId = detail.checkout.successful_payment_id;
            } else if (detail.successful_payment_id) {
                paymentId = detail.successful_payment_id;
            } else if (detail.checkout && detail.checkout.id) {
                paymentId = detail.checkout.id;
            }
        }

        console.log('JustiFi: Payment ID:', paymentId);

        // Send completion to backend
        this._completePayment(paymentId);
    },

    /**
     * Handle payment errors
     */
    _handleErrorEvent: function (detail) {
        console.error('JustiFi: Error event:', detail);

        let message = 'An error occurred. Please try again.';
        if (detail) {
            if (detail.message) {
                message = detail.message;
            } else if (detail.error && detail.error.message) {
                message = detail.error.message;
            } else if (detail.errorCode) {
                message = 'Error: ' + detail.errorCode;
            }
        }

        this._showError(message);
    },

    /**
     * Complete the payment by notifying the backend
     */
    _completePayment: function (paymentId) {
        const self = this;

        // Show loading state
        this._showLoading('Processing payment...');

        jsonrpc(this.apiUrl, {
            checkout_id: this.checkoutId,
            payment_id: paymentId,
            reference: this.reference,
        }).then(function (result) {
            console.log('JustiFi: Complete response:', result);

            if (result.error) {
                self._showError(result.error);
                return;
            }

            if (result.redirect_url) {
                window.location.href = result.redirect_url;
            } else {
                // Fallback redirect
                window.location.href = '/payment/status';
            }
        }).catch(function (error) {
            console.error('JustiFi: Complete error:', error);
            self._showError('Payment processing failed. Please try again.');
        });
    },

    /**
     * Show error message
     */
    _showError: function (message) {
        const errorDiv = this.el.querySelector('#justifi-error');
        const loading = this.el.querySelector('#justifi-loading');
        const wrapper = this.el.querySelector('#justifi-component-wrapper');

        if (loading) loading.style.display = 'none';
        if (wrapper) wrapper.style.display = 'none';

        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
        }
    },

    /**
     * Show loading state
     */
    _showLoading: function (message) {
        const loading = this.el.querySelector('#justifi-loading');
        const wrapper = this.el.querySelector('#justifi-component-wrapper');

        if (wrapper) wrapper.style.display = 'none';

        if (loading) {
            const loadingText = loading.querySelector('p');
            if (loadingText) loadingText.textContent = message || 'Loading...';
            loading.style.display = 'block';
        }
    },
});

export default publicWidget.registry.JustiFiPaymentForm;
