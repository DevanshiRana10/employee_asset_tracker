# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EmployeeAssetAssignment(models.Model):
    _name = 'employee.asset.assignment'
    _description = 'Asset Assignment History'
    _order = 'assigned_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True,
        readonly=True
    )
    asset_id = fields.Many2one(
        'employee.asset',
        string='Asset',
        required=True,
        ondelete='restrict',
        index=True,
        check_company=True
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='restrict',
        index=True,
        check_company=True
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        related='employee_id.department_id',
        store=True,
        readonly=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True
    )
    assigned_by_id = fields.Many2one(
        'res.users',
        string='Assigned By',
        default=lambda self: self.env.user
    )
    returned_to_id = fields.Many2one(
        'res.users',
        string='Received By'
    )
    assigned_date = fields.Date(
        string='Assignment Date',
        default=fields.Date.context_today,
        required=True
    )
    expected_return_date = fields.Date(string='Expected Return Date')
    returned_date = fields.Date(string='Return Date')

    # Aliases for legacy / backward compatibility
    date_assigned = fields.Date(string='Assignment Date (Legacy)', related='assigned_date', readonly=False, store=True)
    date_returned = fields.Date(string='Return Date (Legacy)', related='returned_date', readonly=False, store=True)

    state = fields.Selection(
        [
            ('assigned', 'Assigned'),
            ('returned', 'Returned'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='assigned',
        required=True,
        copy=False,
        index=True
    )
    condition_out = fields.Selection(
        [
            ('new', 'New'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('damaged', 'Damaged'),
        ],
        string='Condition Issued',
        default='good'
    )
    condition_in = fields.Selection(
        [
            ('new', 'New'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('damaged', 'Damaged'),
        ],
        string='Condition Returned'
    )
    notes = fields.Text(string='Notes / Handover Remarks')
    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_is_overdue',
        store=True,
        index=True,
        help='Indicates whether this assignment has exceeded its expected return date'
    )

    @api.depends('state', 'expected_return_date')
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_overdue = bool(rec.state == 'assigned' and rec.expected_return_date and rec.expected_return_date < today)

    @api.depends('asset_id.name', 'employee_id.name', 'assigned_date')
    def _compute_name(self):
        for record in self:
            if record.asset_id and record.employee_id:
                record.name = f"{record.asset_id.name} -> {record.employee_id.name} ({record.assigned_date or 'No Date'})"
            else:
                record.name = "New Assignment"

    @api.model
    def _cron_check_overdue_assignments(self):
        """Daily scheduled action to flag overdue assignments and notify managers."""
        today = fields.Date.today()
        overdue_assignments = self.search([
            ('state', '=', 'assigned'),
            ('expected_return_date', '<', today),
        ])
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for assign in overdue_assignments:
            # Check if alert activity already exists
            existing = self.env['mail.activity'].search_count([
                ('res_id', '=', assign.asset_id.id),
                ('res_model', '=', 'employee.asset'),
                ('summary', 'ilike', 'Overdue Asset Return'),
            ])
            if not existing and activity_type:
                target_user = assign.assigned_by_id or self.env.ref('base.user_admin', raise_if_not_found=False)
                if target_user:
                    assign.asset_id.activity_schedule(
                        activity_type_id=activity_type.id,
                        date_deadline=today,
                        summary=f"Overdue Asset Return: {assign.asset_id.name}",
                        note=f"Asset '{assign.asset_id.name}' assigned to '{assign.employee_id.name}' was scheduled to be returned on {assign.expected_return_date}.",
                        user_id=target_user.id,
                    )
                    assign.asset_id.message_post(
                        body=f"⚠️ <b>Return Alert:</b> Asset is overdue! Expected return date was {assign.expected_return_date}."
                    )

    # --- Constraints ---
    @api.constrains('asset_id', 'state')
    def _check_single_active_assignment(self):
        for rec in self:
            if rec.state == 'assigned':
                active_count = self.search_count([
                    ('asset_id', '=', rec.asset_id.id),
                    ('state', '=', 'assigned'),
                    ('id', '!=', rec.id),
                ])
                if active_count > 0:
                    raise ValidationError(
                        f"Asset '{rec.asset_id.name}' already has an active assignment. "
                        "An asset can have at most one active assignment at a time."
                    )

    @api.constrains('assigned_date', 'expected_return_date')
    def _check_expected_return_date(self):
        for rec in self:
            if rec.assigned_date and rec.expected_return_date and rec.expected_return_date < rec.assigned_date:
                raise ValidationError("Expected return date cannot precede assignment date!")

    @api.constrains('assigned_date', 'returned_date')
    def _check_returned_date(self):
        for rec in self:
            if rec.assigned_date and rec.returned_date and rec.returned_date < rec.assigned_date:
                raise ValidationError("Return date cannot precede assignment date!")

    @api.constrains('asset_id', 'employee_id', 'company_id')
    def _check_company_consistency(self):
        for rec in self:
            if rec.asset_id.company_id and rec.company_id != rec.asset_id.company_id:
                raise ValidationError("Assignment company must match the asset company!")
            if rec.employee_id.company_id and rec.company_id != rec.employee_id.company_id:
                raise ValidationError("Assignment company must match the employee company!")

    @api.constrains('asset_id', 'state')
    def _check_asset_eligibility(self):
        for rec in self:
            if rec.state == 'assigned' and rec.asset_id.state in ('retired', 'lost', 'maintenance'):
                raise ValidationError(
                    f"Cannot assign asset '{rec.asset_id.name}' because it is in '{rec.asset_id.state}' state."
                )

    def action_open_return_wizard(self):
        self.ensure_one()
        if self.state != 'assigned':
            raise UserError("Only active assignments can be returned.")
        return {
            'name': f"Return Asset: {self.asset_id.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'asset.return.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_asset_id': self.asset_id.id,
                'default_assignment_id': self.id,
                'default_condition_in': self.asset_id.condition or self.condition_out,
            },
        }

    def action_cancel(self):
        for rec in self:
            if rec.state == 'returned':
                raise UserError("Cannot cancel an assignment that has already been returned.")
            # If active, release employee from asset and set to available
            if rec.state == 'assigned' and rec.asset_id.employee_id == rec.employee_id:
                rec.asset_id.write({
                    'employee_id': False,
                    'department_id': False,
                    'state': 'available',
                })
            rec.write({'state': 'cancelled'})

    def unlink(self):
        for rec in self:
            if rec.state == 'assigned':
                raise UserError("Cannot delete an active assignment record! Please return or cancel it first.")
        return super().unlink()
