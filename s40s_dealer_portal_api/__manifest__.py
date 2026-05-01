# -*- coding: utf-8 -*-
{
    'name': 'S40S Dealer Portal API',
    'version': '19.0.1.0.0',
    'summary': 'Custom JSON-RPC2 endpoints for the S40S dealer portal (Render-hosted)',
    'description': """
S40S Dealer Portal API
======================

Custom HTTP endpoints consumed by the S40S dealer portal backend on Render.

Endpoints:
- GET /api/v1/dealer/<partner_id>/dashboard
    Returns all dashboard KPIs in one call: open quotes, pending orders,
    revenue MTD, revenue QTD, recent orders, featured products.

- GET /api/v1/dealer/<partner_id>/recent-orders?limit=N
    Recent orders for a dealer's downstream customers.

- GET /api/v1/admin/overview
    Manufacturer-side aggregate KPIs for the Admin Analytics page.

All endpoints use Odoo's native bearer authentication (Authorization: Bearer <api_key>).
The bearer token's user must have read access to sale.order, product.template, etc.

Designed to be consumed by the s40s-dealer-portal Render backend, which scopes
each request to the logged-in dealer's partner_id at the application layer.
    """,
    'category': 'Tools',
    'author': 'Pulse',
    'license': 'LGPL-3',
    'depends': ['sale', 'account', 'stock'],
    'data': [],
    'installable': True,
    'auto_install': False,
}
