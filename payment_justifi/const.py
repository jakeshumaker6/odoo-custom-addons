# Part of Odoo. See LICENSE file for full copyright and licensing details.

# JustiFi API URLs
API_BASE_URL = 'https://api.justifi.ai'
OAUTH_TOKEN_URL = f'{API_BASE_URL}/oauth/token'
CHECKOUTS_URL = f'{API_BASE_URL}/v1/checkouts'
WEB_COMPONENT_TOKEN_URL = f'{API_BASE_URL}/v1/web_component_tokens'
TERMINALS_URL = f'{API_BASE_URL}/v1/terminals'
PAYMENTS_URL = f'{API_BASE_URL}/v1/payments'

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

# JustiFi dispute webhook event names we handle. JustiFi emits both the
# high-level ``payment.disputed`` marker (fires when a previously successful
# payment is challenged — covers credit card chargebacks AND ACH returns,
# since ACH returns are modeled as disputes) and the granular ``dispute.*``
# lifecycle events.
DISPUTE_EVENT_TYPES = (
    'payment.disputed',
    'dispute.created',
    'dispute.updated',
    'dispute.won',
    'dispute.lost',
)

# Dispute status values that mean "money is gone, invoice is no longer paid".
# JustiFi docs don't publicly enumerate dispute statuses, so we match on the
# common industry conventions (Stripe-patterned). Only TERMINAL-LOST statuses
# go here; open/in-progress statuses like ``needs_response`` mean the dispute
# is active but the payment has NOT yet been reversed.
DISPUTE_LOST_STATUSES = ('lost', 'charge_refunded')
DISPUTE_WON_STATUSES = ('won', 'warning_closed')
DISPUTE_OPEN_STATUSES = ('needs_response', 'under_review', 'warning_needs_response')

# ACH-return reason codes (NACHA codes) — used to distinguish ACH returns
# from credit-card chargebacks in chatter messages and customer emails.
ACH_RETURN_REASON_CODES = (
    'R01',  # Insufficient funds
    'R02',  # Account closed
    'R03',  # No account / unable to locate
    'R04',  # Invalid account number
    'R05',  # Unauthorized debit to consumer account
    'R07',  # Authorization revoked by customer
    'R08',  # Payment stopped
    'R09',  # Uncollected funds
    'R10',  # Customer advises not authorized
    'R16',  # Account frozen
    'R20',  # Non-transaction account
    'R29',  # Corporate customer advises not authorized
)
