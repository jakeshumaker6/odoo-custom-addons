# Part of Odoo. See LICENSE file for full copyright and licensing details.

# WooCommerce REST API v3 endpoints (appended to store URL)
WC_API_BASE = 'wp-json/wc/v3'
WC_PRODUCTS_ENDPOINT = f'{WC_API_BASE}/products'
WC_PRODUCT_VARIATIONS_ENDPOINT = f'{WC_API_BASE}/products/{{product_id}}/variations'
WC_PRODUCT_CATEGORIES_ENDPOINT = f'{WC_API_BASE}/products/categories'
WC_PRODUCT_ATTRIBUTES_ENDPOINT = f'{WC_API_BASE}/products/attributes'
WC_PRODUCT_ATTRIBUTE_TERMS_ENDPOINT = f'{WC_API_BASE}/products/attributes/{{attribute_id}}/terms'
WC_ORDERS_ENDPOINT = f'{WC_API_BASE}/orders'
WC_SYSTEM_STATUS_ENDPOINT = f'{WC_API_BASE}/system_status'

# API configuration
DEFAULT_TIMEOUT = 30
WC_BATCH_SIZE = 100  # WooCommerce API max per_page

# Sync directions
SYNC_DIRECTIONS = [
    ('wc_to_odoo', 'WooCommerce → Odoo'),
    ('odoo_to_wc', 'Odoo → WooCommerce'),
    ('both', 'Bidirectional'),
]

# WooCommerce product types
WC_PRODUCT_TYPES = [
    ('simple', 'Simple'),
    ('variable', 'Variable'),
    ('grouped', 'Grouped'),
    ('external', 'External'),
]

# Fields that trigger a sync-needed flag when changed on product.template
SYNC_TRIGGER_FIELDS = {
    'name', 'list_price', 'default_code', 'description_sale',
    'description', 'weight', 'volume', 'categ_id', 'image_1920',
    'active',
}

# Fields that trigger sync on product.product (variant)
VARIANT_SYNC_TRIGGER_FIELDS = {
    'default_code', 'lst_price', 'weight', 'volume', 'image_variant_1920',
    'active',
}
