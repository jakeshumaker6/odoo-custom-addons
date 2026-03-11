# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging

import requests
from requests.auth import HTTPBasicAuth

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from ..const import (
    WC_SYSTEM_STATUS_ENDPOINT,
    WC_PRODUCTS_ENDPOINT,
    WC_PRODUCT_VARIATIONS_ENDPOINT,
    WC_PRODUCT_CATEGORIES_ENDPOINT,
    WC_PRODUCT_ATTRIBUTES_ENDPOINT,
    WC_PRODUCT_ATTRIBUTE_TERMS_ENDPOINT,
    DEFAULT_TIMEOUT,
    WC_BATCH_SIZE,
)

_logger = logging.getLogger(__name__)


class WcBackend(models.Model):
    _name = 'wc.backend'
    _description = 'WooCommerce Backend'
    _order = 'name'

    name = fields.Char(string="Store Name", required=True)
    url = fields.Char(
        string="Store URL",
        required=True,
        help="Your WooCommerce store URL (e.g., https://example.com). No trailing slash.",
    )
    consumer_key = fields.Char(
        string="Consumer Key",
        required=True,
        groups='base.group_system',
        help="WooCommerce REST API Consumer Key (ck_xxxx).",
    )
    consumer_secret = fields.Char(
        string="Consumer Secret",
        required=True,
        groups='base.group_system',
        help="WooCommerce REST API Consumer Secret (cs_xxxx).",
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Connected'),
            ('error', 'Error'),
        ],
        string="Status",
        default='draft',
        readonly=True,
    )
    sync_direction = fields.Selection(
        selection=[
            ('wc_to_odoo', 'WooCommerce → Odoo'),
            ('odoo_to_wc', 'Odoo → WooCommerce'),
            ('both', 'Bidirectional'),
        ],
        string="Sync Direction",
        default='both',
    )

    # Sync timestamps
    last_product_sync = fields.Datetime(string="Last Product Sync", readonly=True)
    last_order_sync = fields.Datetime(string="Last Order Sync", readonly=True)
    last_inventory_sync = fields.Datetime(string="Last Inventory Sync", readonly=True)

    # Sync options
    auto_sync_products = fields.Boolean(string="Auto Sync Products", default=True)
    auto_sync_orders = fields.Boolean(string="Auto Sync Orders", default=True)
    auto_sync_inventory = fields.Boolean(string="Auto Sync Inventory", default=True)
    sync_images = fields.Boolean(string="Sync Images", default=True)
    default_product_type = fields.Selection(
        selection=[
            ('consu', 'Consumable'),
            ('product', 'Storable Product'),
        ],
        string="Default Product Type",
        default='consu',
        help="Odoo product type to use when importing from WooCommerce.",
    )

    company_id = fields.Many2one(
        'res.company',
        string="Company",
        default=lambda self: self.env.company,
    )

    # Sync log
    sync_log_ids = fields.One2many('wc.sync.log', 'backend_id', string="Sync Logs")
    sync_log_count = fields.Integer(
        string="Log Entries",
        compute='_compute_sync_log_count',
    )

    @api.depends('sync_log_ids')
    def _compute_sync_log_count(self):
        for record in self:
            record.sync_log_count = len(record.sync_log_ids)

    # === API HELPER METHODS === #

    def _get_auth(self):
        """Return HTTPBasicAuth for WooCommerce API."""
        self.ensure_one()
        return HTTPBasicAuth(self.consumer_key, self.consumer_secret)

    def _build_url(self, endpoint):
        """Build full URL from store URL and endpoint."""
        self.ensure_one()
        url = self.url.rstrip('/')
        return f'{url}/{endpoint}'

    def _wc_api_get(self, endpoint, params=None):
        """
        Make a GET request to WooCommerce API with pagination support.

        :param endpoint: API endpoint (e.g., 'wp-json/wc/v3/products')
        :param params: Optional query parameters
        :return: List of all results across pages
        """
        self.ensure_one()
        url = self._build_url(endpoint)
        auth = self._get_auth()
        all_results = []
        page = 1
        params = dict(params or {})
        params['per_page'] = WC_BATCH_SIZE

        while True:
            params['page'] = page
            try:
                response = requests.get(url, auth=auth, params=params, timeout=DEFAULT_TIMEOUT)
            except requests.exceptions.RequestException as e:
                _logger.error("WooCommerce GET %s failed: %s", endpoint, str(e))
                raise ValidationError(_("Could not connect to WooCommerce: %s") % str(e))

            if response.status_code >= 400:
                _logger.error(
                    "WooCommerce GET %s error %s: %s",
                    endpoint, response.status_code, response.text[:500]
                )
                raise ValidationError(
                    _("WooCommerce API error %s: %s") % (response.status_code, response.text[:200])
                )

            data = response.json()
            if not data:
                break

            all_results.extend(data)

            # Check if there are more pages
            total_pages = int(response.headers.get('X-WP-TotalPages', 1))
            if page >= total_pages:
                break
            page += 1

        return all_results

    def _wc_api_get_single(self, endpoint, params=None):
        """
        Make a single GET request (no pagination).

        :param endpoint: API endpoint
        :param params: Optional query parameters
        :return: Response JSON dict
        """
        self.ensure_one()
        url = self._build_url(endpoint)
        auth = self._get_auth()

        try:
            response = requests.get(url, auth=auth, params=params, timeout=DEFAULT_TIMEOUT)
        except requests.exceptions.RequestException as e:
            _logger.error("WooCommerce GET %s failed: %s", endpoint, str(e))
            raise ValidationError(_("Could not connect to WooCommerce: %s") % str(e))

        if response.status_code >= 400:
            _logger.error(
                "WooCommerce GET %s error %s: %s",
                endpoint, response.status_code, response.text[:500]
            )
            raise ValidationError(
                _("WooCommerce API error %s: %s") % (response.status_code, response.text[:200])
            )

        return response.json()

    def _wc_api_post(self, endpoint, data):
        """Make a POST request to WooCommerce API."""
        self.ensure_one()
        url = self._build_url(endpoint)
        auth = self._get_auth()

        try:
            response = requests.post(url, auth=auth, json=data, timeout=DEFAULT_TIMEOUT * 2)
        except requests.exceptions.RequestException as e:
            _logger.error("WooCommerce POST %s failed: %s", endpoint, str(e))
            raise ValidationError(_("Could not connect to WooCommerce: %s") % str(e))

        if response.status_code >= 400:
            _logger.error(
                "WooCommerce POST %s error %s: %s",
                endpoint, response.status_code, response.text[:500]
            )
            raise ValidationError(
                _("WooCommerce API error %s: %s") % (response.status_code, response.text[:200])
            )

        return response.json()

    def _wc_api_put(self, endpoint, data):
        """Make a PUT request to WooCommerce API."""
        self.ensure_one()
        url = self._build_url(endpoint)
        auth = self._get_auth()

        try:
            response = requests.put(url, auth=auth, json=data, timeout=DEFAULT_TIMEOUT * 2)
        except requests.exceptions.RequestException as e:
            _logger.error("WooCommerce PUT %s failed: %s", endpoint, str(e))
            raise ValidationError(_("Could not connect to WooCommerce: %s") % str(e))

        if response.status_code >= 400:
            _logger.error(
                "WooCommerce PUT %s error %s: %s",
                endpoint, response.status_code, response.text[:500]
            )
            raise ValidationError(
                _("WooCommerce API error %s: %s") % (response.status_code, response.text[:200])
            )

        return response.json()

    # === ACTION METHODS === #

    def action_test_connection(self):
        """Test the WooCommerce API connection."""
        self.ensure_one()
        _logger.info("WooCommerce: Testing connection to %s", self.url)

        try:
            result = self._wc_api_get_single(WC_SYSTEM_STATUS_ENDPOINT)
            store_info = result.get('environment', {})
            _logger.info(
                "WooCommerce: Connection successful. WC Version: %s, WP Version: %s",
                store_info.get('version', 'unknown'),
                store_info.get('wp_version', 'unknown'),
            )
            self.state = 'confirmed'
            self._create_sync_log('connection', 'import', 'success', 'Connection test successful')
        except (ValidationError, Exception) as e:
            self.state = 'error'
            self._create_sync_log('connection', 'import', 'error', str(e))
            raise

        # Reload the form so the statusbar reflects the new state
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wc.backend',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_sync_products(self):
        """Import products from WooCommerce (categories, attributes, then products)."""
        self.ensure_one()
        _logger.info("WooCommerce: Starting full product sync for %s", self.name)

        try:
            # Step 1: Import categories
            cat_count = self._import_categories()

            # Step 2: Import products (attributes are handled inline)
            prod_count = self._import_products()

            self.last_product_sync = fields.Datetime.now()
            self._create_sync_log(
                'product', 'import', 'success',
                f'Imported {cat_count} categories, {prod_count} products',
            )
        except Exception as e:
            _logger.error("WooCommerce: Product sync failed: %s", str(e))
            self._create_sync_log('product', 'import', 'error', str(e))
            raise

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Product Sync Complete"),
                'message': _("Imported %d categories and %d products.") % (cat_count, prod_count),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_open_sync_logs(self):
        """Open sync log list filtered by this backend."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Sync Logs"),
            'res_model': 'wc.sync.log',
            'view_mode': 'list,form',
            'domain': [('backend_id', '=', self.id)],
            'context': {'default_backend_id': self.id},
        }

    # === IMPORT METHODS === #

    def _import_categories(self):
        """
        Import all product categories from WooCommerce.
        Handles hierarchy by processing parents before children.

        :return: Number of categories imported/updated
        """
        self.ensure_one()
        _logger.info("WooCommerce: Importing categories from %s", self.name)

        wc_categories = self._wc_api_get(WC_PRODUCT_CATEGORIES_ENDPOINT)
        _logger.info("WooCommerce: Fetched %d categories", len(wc_categories))

        ProductCategory = self.env['product.category'].with_context(_wc_importing=True)
        count = 0

        # Sort by parent (0 = root first) to ensure parents exist before children
        wc_categories.sort(key=lambda c: c.get('parent', 0))

        for wc_cat in wc_categories:
            wc_id = wc_cat['id']
            name = wc_cat.get('name', '').strip()
            if not name or name == 'Uncategorized':
                continue

            # Find existing category by wc_id
            odoo_cat = ProductCategory.search([
                ('wc_id', '=', wc_id),
                ('wc_backend_id', '=', self.id),
            ], limit=1)

            # Determine parent
            parent_id = False
            wc_parent = wc_cat.get('parent', 0)
            if wc_parent:
                parent_cat = ProductCategory.search([
                    ('wc_id', '=', wc_parent),
                    ('wc_backend_id', '=', self.id),
                ], limit=1)
                if parent_cat:
                    parent_id = parent_cat.id

            vals = {
                'name': name,
                'wc_id': wc_id,
                'wc_backend_id': self.id,
            }
            if parent_id:
                vals['parent_id'] = parent_id

            if odoo_cat:
                odoo_cat.write(vals)
                _logger.debug("WooCommerce: Updated category %s (wc_id=%d)", name, wc_id)
            else:
                ProductCategory.create(vals)
                _logger.debug("WooCommerce: Created category %s (wc_id=%d)", name, wc_id)

            count += 1

        _logger.info("WooCommerce: Imported/updated %d categories", count)
        return count

    def _import_products(self):
        """
        Import all products from WooCommerce.
        Handles simple and variable products with attributes and variations.

        :return: Number of products imported/updated
        """
        self.ensure_one()
        _logger.info("WooCommerce: Importing products from %s", self.name)

        params = {}
        if self.last_product_sync:
            params['modified_after'] = self.last_product_sync.isoformat()

        wc_products = self._wc_api_get(WC_PRODUCTS_ENDPOINT, params=params)
        _logger.info("WooCommerce: Fetched %d products", len(wc_products))

        count = 0
        for wc_product in wc_products:
            try:
                self._import_single_product(wc_product)
                count += 1
            except Exception as e:
                _logger.error(
                    "WooCommerce: Failed to import product %s (wc_id=%s): %s",
                    wc_product.get('name'), wc_product.get('id'), str(e)
                )
                self._create_sync_log(
                    'product', 'import', 'error',
                    f"Failed to import '{wc_product.get('name')}': {e}",
                )

        _logger.info("WooCommerce: Imported/updated %d products", count)
        return count

    def _import_single_product(self, wc_product):
        """
        Import a single WooCommerce product into Odoo.

        :param wc_product: WooCommerce product dict from API
        """
        self.ensure_one()
        ProductTemplate = self.env['product.template'].with_context(_wc_importing=True)
        wc_id = wc_product['id']
        wc_type = wc_product.get('type', 'simple')

        _logger.info("WooCommerce: Importing product '%s' (wc_id=%d, type=%s)",
                      wc_product.get('name'), wc_id, wc_type)

        # Find existing product by wc_id
        product = ProductTemplate.search([
            ('wc_id', '=', wc_id),
            ('wc_backend_id', '=', self.id),
        ], limit=1)

        # Build product values
        vals = self._prepare_product_vals(wc_product)

        if product:
            product.write(vals)
            _logger.info("WooCommerce: Updated product '%s' (id=%d)", product.name, product.id)
        else:
            product = ProductTemplate.create(vals)
            _logger.info("WooCommerce: Created product '%s' (id=%d)", product.name, product.id)

        # Handle variations for variable products
        if wc_type == 'variable':
            self._import_variations(product, wc_product)

        # Import image
        if self.sync_images:
            self._import_product_image(product, wc_product)

        product.wc_last_synced = fields.Datetime.now()

    def _prepare_product_vals(self, wc_product):
        """
        Prepare Odoo product.template values from WooCommerce product data.

        :param wc_product: WooCommerce product dict
        :return: dict of values for product.template create/write
        """
        self.ensure_one()
        vals = {
            'name': wc_product.get('name', '').strip(),
            'wc_id': wc_product['id'],
            'wc_backend_id': self.id,
            'wc_permalink': wc_product.get('permalink', ''),
            'wc_product_type': wc_product.get('type', 'simple'),
            'type': self.default_product_type,
            'sale_ok': True,
            'purchase_ok': True,
            'active': wc_product.get('status') == 'publish',
        }

        # SKU (only for simple products — variable products have SKU per variation)
        sku = wc_product.get('sku', '').strip()
        if sku and wc_product.get('type') != 'variable':
            vals['default_code'] = sku

        # Price
        regular_price = wc_product.get('regular_price', '')
        if regular_price:
            try:
                vals['list_price'] = float(regular_price)
            except (ValueError, TypeError):
                pass

        # Description
        description = wc_product.get('short_description', '') or wc_product.get('description', '')
        if description:
            vals['description_sale'] = description

        # Weight
        weight = wc_product.get('weight', '')
        if weight:
            try:
                vals['weight'] = float(weight)
            except (ValueError, TypeError):
                pass

        # Categories — assign primary category
        wc_categories = wc_product.get('categories', [])
        if wc_categories:
            # Use the most specific (deepest) category
            for wc_cat in sorted(wc_categories, key=lambda c: c.get('id', 0), reverse=True):
                odoo_cat = self.env['product.category'].search([
                    ('wc_id', '=', wc_cat['id']),
                    ('wc_backend_id', '=', self.id),
                ], limit=1)
                if odoo_cat:
                    vals['categ_id'] = odoo_cat.id
                    break

        return vals

    def _import_variations(self, product, wc_product):
        """
        Import variations for a variable WooCommerce product.
        Sets up attribute lines on the product template and creates/updates variants.

        :param product: Odoo product.template record
        :param wc_product: WooCommerce product dict (parent product)
        """
        self.ensure_one()
        wc_id = wc_product['id']
        endpoint = WC_PRODUCT_VARIATIONS_ENDPOINT.format(product_id=wc_id)

        wc_variations = self._wc_api_get(endpoint)
        _logger.info("WooCommerce: Fetched %d variations for product '%s'",
                      len(wc_variations), product.name)

        if not wc_variations:
            return

        # Step 1: Collect all attributes and their values from the parent product
        wc_attributes = wc_product.get('attributes', [])
        variation_attributes = [a for a in wc_attributes if a.get('variation', False)]

        if not variation_attributes:
            _logger.warning("WooCommerce: Variable product '%s' has no variation attributes", product.name)
            return

        ProductAttribute = self.env['product.attribute'].with_context(_wc_importing=True)
        ProductAttributeValue = self.env['product.attribute.value'].with_context(_wc_importing=True)
        PTAL = self.env['product.template.attribute.line'].with_context(_wc_importing=True)

        # Step 2: Create/find attributes and values, then set up attribute lines
        for wc_attr in variation_attributes:
            attr_name = wc_attr.get('name', '').strip()
            if not attr_name:
                continue

            # Find or create the attribute
            odoo_attr = ProductAttribute.search([('name', '=ilike', attr_name)], limit=1)
            if not odoo_attr:
                odoo_attr = ProductAttribute.create({
                    'name': attr_name,
                    'create_variant': 'always',
                    'wc_id': wc_attr.get('id', 0),
                    'wc_backend_id': self.id,
                })
                _logger.info("WooCommerce: Created attribute '%s'", attr_name)

            # Find or create attribute values
            value_ids = []
            for opt in wc_attr.get('options', []):
                opt_name = opt.strip()
                if not opt_name:
                    continue
                odoo_val = ProductAttributeValue.search([
                    ('name', '=ilike', opt_name),
                    ('attribute_id', '=', odoo_attr.id),
                ], limit=1)
                if not odoo_val:
                    odoo_val = ProductAttributeValue.create({
                        'name': opt_name,
                        'attribute_id': odoo_attr.id,
                    })
                value_ids.append(odoo_val.id)

            if not value_ids:
                continue

            # Find or create attribute line on the product template
            existing_line = PTAL.search([
                ('product_tmpl_id', '=', product.id),
                ('attribute_id', '=', odoo_attr.id),
            ], limit=1)

            if existing_line:
                # Add any new values
                existing_value_ids = set(existing_line.value_ids.ids)
                new_value_ids = set(value_ids) - existing_value_ids
                if new_value_ids:
                    existing_line.write({
                        'value_ids': [(4, vid) for vid in new_value_ids],
                    })
            else:
                PTAL.create({
                    'product_tmpl_id': product.id,
                    'attribute_id': odoo_attr.id,
                    'value_ids': [(6, 0, value_ids)],
                })

        # Step 3: Match WooCommerce variations to Odoo variants
        ProductProduct = self.env['product.product'].with_context(_wc_importing=True)

        for wc_var in wc_variations:
            wc_var_id = wc_var['id']
            wc_var_attrs = wc_var.get('attributes', [])

            # Find the matching Odoo variant by attribute combination
            odoo_variant = self._find_variant_by_attributes(product, wc_var_attrs)

            if odoo_variant:
                # Update variant fields
                var_vals = {
                    'wc_variant_id': wc_var_id,
                }

                # SKU
                sku = wc_var.get('sku', '').strip()
                if sku:
                    var_vals['default_code'] = sku

                # Price
                regular_price = wc_var.get('regular_price', '')
                if regular_price:
                    try:
                        var_vals['wc_price'] = float(regular_price)
                    except (ValueError, TypeError):
                        pass

                # Weight
                weight = wc_var.get('weight', '')
                if weight:
                    try:
                        var_vals['weight'] = float(weight)
                    except (ValueError, TypeError):
                        pass

                odoo_variant.write(var_vals)
                _logger.debug("WooCommerce: Updated variant %s (wc_var_id=%d)", odoo_variant.display_name, wc_var_id)

                # Import variant image
                if self.sync_images:
                    self._import_variant_image(odoo_variant, wc_var)
            else:
                _logger.warning(
                    "WooCommerce: Could not find matching variant for wc_var_id=%d on product '%s'. Attrs: %s",
                    wc_var_id, product.name, wc_var_attrs,
                )

    def _find_variant_by_attributes(self, product, wc_var_attrs):
        """
        Find the Odoo product.product variant matching the WooCommerce attribute combination.

        :param product: Odoo product.template
        :param wc_var_attrs: List of WC variation attribute dicts [{'name': 'Size', 'option': 'Large'}]
        :return: product.product record or False
        """
        if not wc_var_attrs:
            # If no attributes specified, return first variant
            return product.product_variant_ids[:1]

        for variant in product.product_variant_ids:
            match = True
            for wc_attr in wc_var_attrs:
                attr_name = wc_attr.get('name', '').strip()
                attr_value = wc_attr.get('option', '').strip()
                if not attr_name or not attr_value:
                    continue

                # Check if this variant has this attribute value
                found = False
                for ptav in variant.product_template_attribute_value_ids:
                    if (ptav.attribute_id.name.lower() == attr_name.lower() and
                            ptav.product_attribute_value_id.name.lower() == attr_value.lower()):
                        found = True
                        break
                if not found:
                    match = False
                    break

            if match:
                return variant

        return False

    def _import_product_image(self, product, wc_product):
        """
        Download and set the main product image from WooCommerce.

        :param product: Odoo product.template record
        :param wc_product: WooCommerce product dict
        """
        images = wc_product.get('images', [])
        if not images:
            return

        main_image = images[0]
        image_url = main_image.get('src', '')
        if not image_url:
            return

        try:
            response = requests.get(image_url, timeout=DEFAULT_TIMEOUT)
            if response.status_code == 200:
                image_data = base64.b64encode(response.content)
                product.with_context(_wc_importing=True).image_1920 = image_data
                _logger.debug("WooCommerce: Downloaded image for product '%s'", product.name)
            else:
                _logger.warning("WooCommerce: Failed to download image from %s (status %d)",
                                image_url, response.status_code)
        except requests.exceptions.RequestException as e:
            _logger.warning("WooCommerce: Image download error for '%s': %s", product.name, str(e))

    def _import_variant_image(self, variant, wc_variation):
        """
        Download and set variant-specific image.

        :param variant: Odoo product.product record
        :param wc_variation: WooCommerce variation dict
        """
        image_data = wc_variation.get('image', {})
        if not image_data:
            return

        image_url = image_data.get('src', '')
        if not image_url:
            return

        try:
            response = requests.get(image_url, timeout=DEFAULT_TIMEOUT)
            if response.status_code == 200:
                variant.with_context(_wc_importing=True).image_variant_1920 = base64.b64encode(response.content)
        except requests.exceptions.RequestException as e:
            _logger.warning("WooCommerce: Variant image download error: %s", str(e))

    # === CRON METHODS === #

    @api.model
    def _cron_sync_products(self):
        """Called by cron to sync products for all active backends."""
        backends = self.search([
            ('state', '=', 'confirmed'),
            ('auto_sync_products', '=', True),
        ])
        for backend in backends:
            _logger.info("WooCommerce: Cron product sync for '%s'", backend.name)
            try:
                backend.action_sync_products()
            except Exception as e:
                _logger.error("WooCommerce: Cron product sync failed for '%s': %s",
                              backend.name, str(e))
                backend._create_sync_log('product', 'import', 'error', f'Cron sync failed: {e}')

    # === LOG HELPER === #

    def _create_sync_log(self, sync_type, direction, status, message, record_count=0):
        """Create a sync log entry."""
        self.ensure_one()
        self.env['wc.sync.log'].sudo().create({
            'backend_id': self.id,
            'sync_type': sync_type,
            'direction': direction,
            'status': status,
            'message': message,
            'record_count': record_count,
        })
