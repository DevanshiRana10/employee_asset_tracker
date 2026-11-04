# -*- coding: utf-8 -*-

from odoo import fields, models


class AssetReturnWizard(models.TransientModel):
    _name = 'asset.return.wizard'
    _description = 'Asset Return Wizard'

    asset_id = fields.Many2one(
        'employee.asset',
        string='Asset',
        required=True
    )
    assignment_id = fields.Many2one(
        'employee.asset.assignment',
        string='Active Assignment'
    )
    returned_date = fields.Date(
        string='Return Date',
        default=fields.Date.context_today,
        required=True
    )
    returned_to_id = fields.Many2one(
        'res.users',
        string='Received By',
        default=lambda self: self.env.user,
        required=True
    )
    condition_in = fields.Selection(
        [
            ('new', 'New'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('damaged', 'Damaged'),
        ],
        string='Returned Condition',
        default='good',
        required=True
    )
    next_state = fields.Selection(
        [
            ('available', 'Available (Fit for reuse)'),
            ('maintenance', 'Under Maintenance (Requires repair)'),
        ],
        string='Next Lifecycle State',
        default='available',
        required=True
    )
    notes = fields.Text(string='Return / Inspection Notes')

    def action_confirm_return(self):
        self.ensure_one()
        self.asset_id.action_return_asset(
            returned_date=self.returned_date,
            returned_to_id=self.returned_to_id,
            condition_in=self.condition_in,
            next_state=self.next_state,
            notes=self.notes,
        )
        return {'type': 'ir.actions.act_window_close'}
