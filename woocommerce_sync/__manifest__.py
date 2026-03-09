# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'WooCommerce Sync',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Bidirectional product, order, and inventory sync with WooCommerce.',
    'description': """
WooCommerce Sync for Odoo
=========================

This module provides bidirectional synchronization between WooCommerce and Odoo,
allowing you to manage products, orders, and inventory across both platforms.

Features:
- Import products from WooCommerce (including variable products with attributes)
- Import categories and product attributes
- Import product images
- Bidirectional product sync via scheduled jobs
- Order import from WooCommerce
- Inventory sync from Odoo to WooCommerce
- Sync log for monitoring and troubleshooting

Configuration:
1. Go to Sales → WooCommerce → Configuration
2. Create a new WooCommerce Backend with your store URL and API credentials
3. Click "Test Connection" to verify
4. Use "Sync Products" to import your catalog
    """,
    'author': 'Jake Shumaker at Pulse Marketing',
    'website': 'https://pulsemktg.com',
    'depends': ['sale_management', 'stock', 'product'],
    'data': [
        'security/woocommerce_sync_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/wc_backend_views.xml',
        'views/wc_sync_log_views.xml',
        'views/product_template_views.xml',
        'views/product_category_views.xml',
        'views/menus.xml',
    ],
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
