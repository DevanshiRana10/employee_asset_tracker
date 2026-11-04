# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EmployeeAssetMaintenance(models.Model):
    _name = 'employee.asset.maintenance'
    _description = 'Asset Maintenance'
    _order = 'reported_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Maintenance Subject', required=True)
    asset_id = fields.Many2one(
        'employee.asset',
        string='Asset',
        required=True,
        ondelete='restrict',
        index=True,
        check_company=True
    )
    maintenance_type = fields.Selection(
        [
            ('preventive', 'Preventive Maintenance'),
            ('corrective', 'Corrective / Repair'),
        ],
        string='Maintenance Type',
        default='preventive',
        required=True
    )
    description = fields.Text(string='Work Description', required=True)
    reported_date = fields.Date(
        string='Reported Date',
        default=fields.Date.context_today,
        required=True
    )
    scheduled_date = fields.Date(string='Scheduled Date')
    start_date = fields.Date(string='Start Date')
    completion_date = fields.Date(string='Completion Date')

    # Aliases for backwards compatibility with earlier views/tests
    date_scheduled = fields.Date(string='Scheduled Date (Legacy)', related='scheduled_date', readonly=False, store=True)
    date_completed = fields.Date(string='Completion Date (Legacy)', related='completion_date', readonly=False, store=True)

    technician_id = fields.Many2one(
        'res.users',
        string='Technician',
        default=lambda self: self.env.user
    )
    vendor_id = fields.Many2one(
        'res.partner',
        string='Service Provider / Vendor',
        domain="[('is_company', '=', True)]",
        check_company=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor (Legacy)',
        related='vendor_id',
        readonly=False,
        store=True
    )
    cost = fields.Monetary(
        string='Maintenance Cost',
        default=0.0,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        compute='_compute_currency_id',
        store=True,
        readonly=False,
        precompute=True
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('scheduled', 'Scheduled'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        copy=False,
        index=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True
    )
    resolution_notes = fields.Text(string='Resolution Notes')
    notes = fields.Text(string='Internal Notes', related='resolution_notes', readonly=False)

    @api.depends('company_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = rec.company_id.currency_id or self.env.company.currency_id

    # --- Constraints ---
    @api.constrains('cost')
    def _check_cost(self):
        for rec in self:
            if rec.cost < 0:
                raise ValidationError("Maintenance cost cannot be negative!")

    @api.constrains('reported_date', 'scheduled_date', 'start_date', 'completion_date')
    def _check_dates(self):
        for rec in self:
            if rec.scheduled_date and rec.reported_date and rec.scheduled_date < rec.reported_date:
                raise ValidationError("Scheduled date cannot precede reported date!")
            if rec.start_date and rec.reported_date and rec.start_date < rec.reported_date:
                raise ValidationError("Start date cannot precede reported date!")
            if rec.completion_date and rec.start_date and rec.completion_date < rec.start_date:
                raise ValidationError("Completion date cannot precede start date!")

    @api.constrains('asset_id', 'company_id')
    def _check_company_consistency(self):
        for rec in self:
            if rec.asset_id.company_id and rec.company_id != rec.asset_id.company_id:
                raise ValidationError("Maintenance company must match the asset company!")

    # --- Workflow Methods ---
    def action_schedule(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Only draft maintenance records can be scheduled.")
            rec.write({'state': 'scheduled'})

    def action_start(self):
        for rec in self:
            if rec.state not in ('draft', 'scheduled'):
                raise UserError(f"Cannot start maintenance from '{rec.state}' state.")
            if rec.asset_id.state in ('retired', 'lost'):
                raise UserError(f"Cannot perform maintenance on an asset that is '{rec.asset_id.state}'.")
            if rec.asset_id.state == 'assigned' or rec.asset_id.employee_id:
                raise UserError(
                    f"Asset '{rec.asset_id.name}' is currently assigned to '{rec.asset_id.employee_id.name}'. "
                    "You must return or resolve the active assignment before starting maintenance."
                )

            today = fields.Date.context_today(rec)
            rec.write({
                'state': 'in_progress',
                'start_date': rec.start_date or today,
            })
            rec.asset_id.write({'state': 'maintenance'})
            rec.asset_id.message_post(body=f"Maintenance '{rec.name}' started. Asset status set to Under Maintenance.")

    def action_complete(self):
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError("Only maintenance in progress can be marked as completed.")

            today = fields.Date.context_today(rec)
            rec.write({
                'state': 'completed',
                'completion_date': rec.completion_date or today,
            })

            # Check if other maintenance is still in progress for this asset
            other_in_progress = self.search_count([
                ('asset_id', '=', rec.asset_id.id),
                ('id', '!=', rec.id),
                ('state', '=', 'in_progress'),
            ])

            # Recalculate asset state safely
            if other_in_progress == 0:
                if rec.asset_id.state not in ('retired', 'lost'):
                    rec.asset_id.write({'state': 'available'})
                    rec.asset_id.message_post(body=f"Maintenance '{rec.name}' completed. Asset returned to Available.")
                else:
                    rec.asset_id.message_post(body=f"Maintenance '{rec.name}' completed. Asset remains {rec.asset_id.state}.")

    def action_cancel(self):
        for rec in self:
            if rec.state == 'completed':
                raise UserError("Completed maintenance records cannot be cancelled.")

            was_in_progress = (rec.state == 'in_progress')
            rec.write({'state': 'cancelled'})

            if was_in_progress:
                # Recalculate asset state
                other_in_progress = self.search_count([
                    ('asset_id', '=', rec.asset_id.id),
                    ('id', '!=', rec.id),
                    ('state', '=', 'in_progress'),
                ])
                if other_in_progress == 0 and rec.asset_id.state == 'maintenance':
                    rec.asset_id.write({'state': 'available'})
                    rec.asset_id.message_post(body=f"Maintenance '{rec.name}' cancelled. Asset returned to Available.")
