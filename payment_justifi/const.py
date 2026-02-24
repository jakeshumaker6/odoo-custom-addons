# Part of Odoo. See LICENSE file for full copyright and licensing details.

# JustiFi API URLs
API_BASE_URL = 'https://api.justifi.ai'
OAUTH_TOKEN_URL = f'{API_BASE_URL}/oauth/token'
CHECKOUTS_URL = f'{API_BASE_URL}/v1/checkouts'
WEB_COMPONENT_TOKEN_URL = f'{API_BASE_URL}/v1/web_component_tokens'

# JustiFi Web Components CDN
WEBCOMPONENTS_CDN_URL = 'https://cdn.jsdelivr.net/npm/@justifi/webcomponents@latest/dist/webcomponents/webcomponents.esm.js'

# Supported currencies
SUPPORTED_CURRENCIES = ['USD']

# Payment method codes
PAYMENT_METHOD_CODES_CARD = ['card']
PAYMENT_METHOD_CODES_ACH = ['bank_sepa']  # ACH/bank transfer
PAYMENT_METHOD_CODES_BOTH = ['card', 'bank_sepa']

# Transaction states mapping from JustiFi to Odoo
STATUS_MAPPING = {
    'completed': 'done',
    'succeeded': 'done',
    'pending': 'pending',
    'created': 'pending',
    'failed': 'error',
    'canceled': 'cancel',
}
