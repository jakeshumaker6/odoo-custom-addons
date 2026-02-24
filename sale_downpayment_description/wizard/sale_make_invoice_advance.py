# -*- coding: utf-8 -*-
from odoo import models


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    def _prepare_down_payment_invoice_line_values(self, order, so_line, account):
        """
        Override to include product names from the Sales Order in the
        down payment invoice line description.
        """
        # Get the base values from parent
        values = super()._prepare_down_payment_invoice_line_values(order, so_line, account)

        # Generate enhanced description with product names
        description = self._generate_down_payment_description(order)
        if description:
            values['name'] = description

        return values

    def _generate_down_payment_description(self, order):
        """
        Generate a descriptive text for down payment that includes
        the products from the Sales Order.

        Returns something like:
            "Deposit (50%) for: Product A, Product B, Product C
            Order: S00001"
        """
        # Collect product names from order lines (excluding section/note lines)
        product_names = []
        for line in order.order_line:
            # Skip display-only lines (sections, notes) and lines without products
            if not line.display_type and line.product_id:
                product_names.append(line.product_id.name)

        # Build products string (show up to 5, then "+X more")
        if product_names:
            products_str = ', '.join(product_names[:5])
            if len(product_names) > 5:
                products_str += f' (+{len(product_names) - 5} more)'
        else:
            products_str = ''

        # Build base text based on payment method
        if self.advance_payment_method == 'percentage':
            # Format percentage cleanly (50.0 -> "50%", 33.33 -> "33.33%")
            amount_str = f"{self.amount:g}"  # Removes trailing zeros
            base_text = f"Deposit ({amount_str}%)"
        else:
            base_text = "Deposit"

        # Combine into final description
        if products_str:
            description = f"{base_text} for: {products_str}"
        else:
            description = base_text

        # Add order reference
        description += f"\nOrder: {order.name}"

        return description
