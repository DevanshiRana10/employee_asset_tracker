# -*- coding: utf-8 -*-

from odoo import fields, models


class AssetAssignWizard(models.TransientModel):
    _name = 'asset.assign.wizard'
    _description = 'Asset Assignment Wizard'

    asset_id = fields.Many2one(
        'employee.asset',
        string='Asset',
        required=True
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee to Assign',
        required=True
    )
    assigned_date = fields.Date(
        string='Assignment Date',
        default=fields.Date.context_today,
        required=True
    )
    expected_return_date = fields.Date(string='Expected Return Date')
    condition_out = fields.Selection(
        [
            ('new', 'New'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('damaged', 'Damaged'),
        ],
        string='Issue Condition',
        default='good',
        required=True
    )
    notes = fields.Text(string='Handover Notes')

    def action_confirm_assign(self):
        self.ensure_one()
        self.asset_id.action_assign_asset(
            employee=self.employee_id,
            assigned_date=self.assigned_date,
            expected_return_date=self.expected_return_date,
            condition_out=self.condition_out,
            notes=self.notes,
        )
        return {'type': 'ir.actions.act_window_close'}
