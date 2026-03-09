# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class WcSyncLog(models.Model):
    _name = 'wc.sync.log'
    _description = 'WooCommerce Sync Log'
    _order = 'create_date desc'

    backend_id = fields.Many2one(
        'wc.backend',
        string="Backend",
        required=True,
        ondelete='cascade',
    )
    sync_type = fields.Selection(
        selection=[
            ('connection', 'Connection'),
            ('product', 'Product'),
            ('category', 'Category'),
            ('attribute', 'Attribute'),
            ('order', 'Order'),
            ('inventory', 'Inventory'),
        ],
        string="Type",
        required=True,
    )
    direction = fields.Selection(
        selection=[
            ('import', 'Import (WC → Odoo)'),
            ('export', 'Export (Odoo → WC)'),
        ],
        string="Direction",
        required=True,
    )
    status = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('warning', 'Warning'),
            ('error', 'Error'),
        ],
        string="Status",
        required=True,
    )
    message = fields.Char(string="Message")
    details = fields.Text(string="Details")
    record_count = fields.Integer(string="Records Affected")
