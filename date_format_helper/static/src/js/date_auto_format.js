/** @odoo-module */

/**
 * Date Auto-Format Helper
 *
 * Automatically inserts date separators as the user types numeric-only dates.
 * Allows typing "021906" to get "02/19/06" - similar to QuickBooks Online.
 *
 * Supports US date format: MM/DD/YY or MM/DD/YYYY
 */

import { patch } from "@web/core/utils/patch";
import { DateTimeInput } from "@web/core/datetime/datetime_input";

/**
 * Auto-format a numeric string into MM/DD/YY or MM/DD/YYYY format.
 *
 * @param {string} value - The numeric input value
 * @returns {string} - Formatted date string with slashes
 */
function autoFormatDate(value) {
    // Remove any existing separators to get pure digits
    const digits = value.replace(/\D/g, '');

    if (digits.length === 0) {
        return value;
    }

    // Build formatted string progressively
    let formatted = '';

    // Month (1-2 digits)
    if (digits.length >= 1) {
        formatted = digits.substring(0, Math.min(2, digits.length));
    }

    // Add slash after month if we have day digits
    if (digits.length > 2) {
        formatted += '/' + digits.substring(2, Math.min(4, digits.length));
    }

    // Add slash after day if we have year digits
    if (digits.length > 4) {
        formatted += '/' + digits.substring(4, Math.min(8, digits.length));
    }

    return formatted;
}

/**
 * Check if a string contains only digits (no separators).
 *
 * @param {string} value - The input value
 * @returns {boolean} - True if numeric only
 */
function isNumericOnly(value) {
    return /^\d+$/.test(value);
}

/**
 * Patch the DateTimeInput component to auto-format numeric date input.
 */
patch(DateTimeInput.prototype, {
    /**
     * Handle input changes and auto-format if needed.
     */
    onInput(ev) {
        const input = ev.target;
        const value = input.value;
        const cursorPos = input.selectionStart;

        // Only auto-format if the input is pure numeric (no slashes yet)
        // and has enough digits to warrant formatting
        if (isNumericOnly(value) && value.length >= 3) {
            const formatted = autoFormatDate(value);

            if (formatted !== value) {
                input.value = formatted;

                // Calculate new cursor position
                // Account for added slashes
                const addedChars = formatted.length - value.length;
                const newPos = Math.min(cursorPos + addedChars, formatted.length);
                input.setSelectionRange(newPos, newPos);
            }
        }

        // Call original method if it exists
        if (super.onInput) {
            super.onInput(ev);
        }
    },
});

/**
 * Also add a global listener as a fallback for date inputs that might not
 * use the DateTimeInput component directly.
 */
document.addEventListener('input', (ev) => {
    const input = ev.target;

    // Check if this is a date-related input field
    // Look for inputs with date-related classes or attributes
    if (input.tagName !== 'INPUT') {
        return;
    }

    const isDateInput = (
        input.classList.contains('o_datepicker_input') ||
        input.classList.contains('o_input_date') ||
        input.closest('.o_datetime_picker') ||
        input.closest('.o_datepicker') ||
        input.getAttribute('data-field-type') === 'date' ||
        input.getAttribute('data-field-type') === 'datetime'
    );

    if (!isDateInput) {
        return;
    }

    const value = input.value;
    const cursorPos = input.selectionStart;

    // Only auto-format pure numeric input with at least 3 digits
    if (isNumericOnly(value) && value.length >= 3) {
        const formatted = autoFormatDate(value);

        if (formatted !== value) {
            input.value = formatted;

            // Adjust cursor position for added slashes
            const addedChars = formatted.length - value.length;
            const newPos = Math.min(cursorPos + addedChars, formatted.length);
            input.setSelectionRange(newPos, newPos);

            // Trigger input event for Odoo's reactive system
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }
}, true);

console.log('Date Format Helper: Auto-format enabled for date inputs');
