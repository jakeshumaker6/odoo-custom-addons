from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    deposit_count = fields.Integer(
        string='Active Deposits',
        compute='_compute_deposit_count',
    )

    def _compute_deposit_count(self):
        for partner in self:
            partner.deposit_count = self.env['pos.order'].search_count([
                ('partner_id', '=', partner.id),
                ('is_deposit', '=', True),
                ('deposit_state', '=', 'active'),
            ])

    def action_view_deposits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Customer Deposits',
            'res_model': 'pos.order',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id', '=', self.id),
                ('is_deposit', '=', True),
            ],
            'context': {'default_partner_id': self.id},
        }
