# Odoo Custom Addons

Custom Odoo modules for deployment via Odoo.sh.

## Modules

### payment_justifi

JustiFi Payment Provider for Odoo 19 Enterprise.

**Features:**
- Card payments via JustiFi modular checkout component
- Customer portal integration for invoice payments
- Webhook support for real-time payment status updates
- Secure tokenization (no card data stored in Odoo)

**Configuration:**
1. Install the module via Apps menu
2. Go to Invoicing → Configuration → Payment Providers
3. Select JustiFi and enter your credentials:
   - Client ID
   - Client Secret
   - Sub-Account ID (acc_...)
   - Payment Method Group ID (pmg_...)
4. Set state to "Test" or "Enabled"

**Webhook URL:**
```
https://your-odoo-domain/payment/justifi/webhook
```

## Deployment to Odoo.sh

1. Connect this repository to your Odoo.sh project
2. Push to your staging branch to test
3. Merge to production when ready

## License

LGPL-3
