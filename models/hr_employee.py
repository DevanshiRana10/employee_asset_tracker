# -*- coding: utf-8 -*-

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    assigned_asset_ids = fields.One2many(
        'employee.asset',
        'employee_id',
        string='Assigned Assets',
        domain=[('state', '=', 'assigned')]
    )
    asset_count = fields.Integer(
        string='Assets Held',
        compute='_compute_asset_count',
        help='Number of active company assets currently held by this employee'
    )

    @api.depends('assigned_asset_ids')
    def _compute_asset_count(self):
        for employee in self:
            employee.asset_count = len(employee.assigned_asset_ids)

    def action_view_assigned_assets(self):
        self.ensure_one()
        return {
            'name': f"Assets Assigned to {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'employee.asset',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id), ('state', '=', 'assigned')],
            'context': {
                'default_employee_id': self.id,
                'default_company_id': self.company_id.id if self.company_id else False,
            },
        }
