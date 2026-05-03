# -*- coding: utf-8 -*-
from datetime import date

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request


def _quarter_bounds(today):
    """Return (start, end_exclusive) date pair for the calendar quarter `today` falls in."""
    q_start_month = ((today.month - 1) // 3) * 3 + 1
    start = date(today.year, q_start_month, 1)
    end_month = q_start_month + 3
    end_year = today.year + (1 if end_month > 12 else 0)
    end_month = end_month if end_month <= 12 else end_month - 12
    end = date(end_year, end_month, 1)
    return start, end


def _month_bounds(today):
    """Return (start, end_exclusive) date pair for the calendar month `today` falls in."""
    start = date(today.year, today.month, 1)
    end_year = today.year + (1 if today.month == 12 else 0)
    end_month = 1 if today.month == 12 else today.month + 1
    end = date(end_year, end_month, 1)
    return start, end


class DealerPortalAPI(http.Controller):
    """
    HTTP endpoints for the S40S dealer portal backend (Render).

    Auth: Authorization: Bearer <api_key>
    The token's user determines DB-level permissions; the portal backend
    is responsible for application-level scoping (which dealer is asking).
    """

    @http.route('/api/v1/dealer/<int:partner_id>/dashboard',
                type='json2', auth='bearer', methods=['GET', 'POST'], readonly=True)
    def dealer_dashboard(self, partner_id):
        partner = request.env['res.partner'].browse(partner_id).exists()
        if not partner:
            return {'error': 'partner_not_found', 'partner_id': partner_id}

        Order = request.env['sale.order']
        Product = request.env['product.template']

        scope = [('partner_id', 'child_of', partner_id)]

        today = date.today()
        m_start, m_end = _month_bounds(today)
        q_start, q_end = _quarter_bounds(today)

        open_quotes = Order.search_count(
            scope + [('state', 'in', ('draft', 'sent'))]
        )
        pending_orders = Order.search_count(
            scope + [('state', '=', 'sale')]
        )

        revenue_mtd_orders = Order.search_read(
            scope + [('state', '=', 'sale'),
                     ('date_order', '>=', m_start.isoformat()),
                     ('date_order', '<', m_end.isoformat())],
            ['amount_total'],
        )
        revenue_qtd_orders = Order.search_read(
            scope + [('state', '=', 'sale'),
                     ('date_order', '>=', q_start.isoformat()),
                     ('date_order', '<', q_end.isoformat())],
            ['amount_total'],
        )

        recent = Order.search_read(
            scope + [('state', 'in', ('sale', 'done'))],
            ['id', 'name', 'partner_id', 'date_order', 'amount_total', 'state', 'delivery_status'],
            limit=5, order='date_order desc',
        )

        featured = Product.search_read(
            [('active', '=', True), ('sale_ok', '=', True)],
            ['id', 'name', 'list_price'],
            limit=4, order='create_date desc',
        )

        return {
            'partner': {'id': partner.id, 'name': partner.name},
            'kpis': {
                'open_quotes': open_quotes,
                'pending_orders': pending_orders,
                'revenue_mtd': sum(o['amount_total'] for o in revenue_mtd_orders),
                'revenue_qtd': sum(o['amount_total'] for o in revenue_qtd_orders),
            },
            'recent_orders': recent,
            'featured_products': featured,
        }

    @http.route('/api/v1/dealer/<int:partner_id>/recent-orders',
                type='json2', auth='bearer', methods=['GET', 'POST'], readonly=True)
    def dealer_recent_orders(self, partner_id, limit=10):
        Order = request.env['sale.order']
        scope = [('partner_id', 'child_of', partner_id),
                 ('state', 'in', ('sale', 'done'))]
        return Order.search_read(
            scope,
            ['id', 'name', 'partner_id', 'date_order', 'amount_total', 'state', 'delivery_status'],
            limit=int(limit), order='date_order desc',
        )

    @http.route('/api/v1/admin/overview',
                type='json2', auth='bearer', methods=['GET', 'POST'], readonly=True)
    def admin_overview(self):
        if not request.env.user.has_group('sales_team.group_sale_manager'):
            raise AccessError("This endpoint requires Sales Manager privileges")

        Partner = request.env['res.partner']
        Order = request.env['sale.order']

        total_dealers = Partner.search_count(
            [('customer_rank', '>', 0), ('active', '=', True)]
        )
        revenue_orders = Order.search_read(
            [('state', '=', 'sale')],
            ['amount_total'],
        )
        revenue_total = sum(o['amount_total'] for o in revenue_orders)

        all_quotes = Order.search_count([('state', 'in', ('draft', 'sent', 'sale'))])
        confirmed = Order.search_count([('state', '=', 'sale')])
        conversion_rate = (confirmed / all_quotes) if all_quotes else 0.0

        top_dealers = Order.read_group(
            [('state', '=', 'sale')],
            ['amount_total:sum'],
            ['partner_id'],
            orderby='amount_total desc',
            limit=10,
        )

        return {
            'total_dealers': total_dealers,
            'revenue_total': revenue_total,
            'conversion_rate': round(conversion_rate, 4),
            'top_dealers': top_dealers,
        }
