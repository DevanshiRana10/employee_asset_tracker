# -*- coding: utf-8 -*-

from datetime import timedelta
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EmployeeAsset(models.Model):
    _name = 'employee.asset'
    _description = 'Employee Asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name, id desc'
    _check_company_auto = True

    # --- 1. Identification ---
    name = fields.Char(string='Asset Name', required=True, tracking=True)
    asset_code = fields.Char(
        string='Asset Code',
        required=True,
        copy=False,
        index=True,
        tracking=True,
        help='Unique internal asset tracking identifier'
    )
    barcode = fields.Char(
        string='Barcode / QR Code',
        copy=False,
        index=True,
        help='Unique barcode or QR code value for physical tagging and scanning'
    )
    serial_number = fields.Char(
        string='Serial Number',
        copy=False,
        index=True,
        tracking=True,
        help='Manufacturer serial number'
    )
    category_id = fields.Many2one(
        'employee.asset.category',
        string='Category',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        check_company=True
    )
    description = fields.Text(string='Description')
    image_1920 = fields.Image(string='Asset Image', max_width=1920, max_height=1920)

    # --- 2. Purchase & Financial Details ---
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor / Supplier',
        domain="[('is_company', '=', True)]",
        check_company=True
    )
    purchase_date = fields.Date(string='Purchase Date')
    purchase_price = fields.Monetary(
        string='Purchase Price',
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
    warranty_end_date = fields.Date(string='Warranty End Date')
    warranty_status = fields.Selection(
        [
            ('valid', 'Under Warranty'),
            ('expiring', 'Expiring Soon (30d)'),
            ('expired', 'Expired'),
            ('none', 'No Warranty Specified'),
        ],
        string='Warranty Status',
        compute='_compute_warranty_status',
        store=True,
        index=True
    )
    purchase_reference = fields.Char(string='Invoice / Purchase Reference')

    # --- 3. Assignment & Organizational Details ---
    employee_id = fields.Many2one(
        'hr.employee',
        string='Current Employee',
        index=True,
        tracking=True,
        readonly=True,
        check_company=True,
        help='Employee currently assigned to this asset'
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        compute='_compute_department_id',
        store=True,
        readonly=True,
        check_company=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True
    )
    location = fields.Char(string='Physical Location', help='Office, floor, or specific site')

    # --- 4. Bundling & Peripherals ---
    parent_id = fields.Many2one(
        'employee.asset',
        string='Parent Bundle',
        index=True,
        ondelete='set null',
        check_company=True,
        help='Optional parent asset if this item is part of a bundled package (e.g. Monitor bundled with PC)'
    )
    child_ids = fields.One2many(
        'employee.asset',
        'parent_id',
        string='Bundled Sub-Assets'
    )
    child_count = fields.Integer(
        string='Bundled Items',
        compute='_compute_bundle_counts',
        store=False
    )
    accessory_ids = fields.One2many(
        'employee.asset.accessory',
        'asset_id',
        string='Accessories & Peripherals'
    )
    accessory_count = fields.Integer(
        string='Accessories',
        compute='_compute_bundle_counts',
        store=False
    )

    # --- 5. Lifecycle & Condition ---
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('available', 'Available'),
            ('assigned', 'Assigned'),
            ('maintenance', 'Under Maintenance'),
            ('retired', 'Retired'),
            ('lost', 'Lost'),
        ],
        string='Status',
        default='draft',
        required=True,
        copy=False,
        index=True,
        tracking=True,
        readonly=True
    )
    condition = fields.Selection(
        [
            ('new', 'New'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('damaged', 'Damaged'),
        ],
        string='Condition',
        default='new',
        tracking=True
    )
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Internal Remarks')
    is_overdue = fields.Boolean(
        string='Return Overdue',
        compute='_compute_is_overdue',
        store=True,
        index=True
    )

    # --- 6. Relationships & Counts ---
    assignment_ids = fields.One2many(
        'employee.asset.assignment',
        'asset_id',
        string='Assignment History'
    )
    maintenance_ids = fields.One2many(
        'employee.asset.maintenance',
        'asset_id',
        string='Maintenance Records'
    )
    active_assignment_id = fields.Many2one(
        'employee.asset.assignment',
        string='Active Assignment',
        compute='_compute_active_assignment_id',
        store=True
    )
    assignment_count = fields.Integer(
        string='Assignment Count',
        compute='_compute_counts',
        store=False
    )
    maintenance_count = fields.Integer(
        string='Maintenance Count',
        compute='_compute_counts',
        store=False
    )

    # --- Computations ---
    @api.depends('company_id')
    def _compute_currency_id(self):
        for asset in self:
            asset.currency_id = asset.company_id.currency_id or self.env.company.currency_id

    @api.depends('employee_id.department_id')
    def _compute_department_id(self):
        for asset in self:
            asset.department_id = asset.employee_id.department_id if asset.employee_id else False

    @api.depends('assignment_ids.state')
    def _compute_active_assignment_id(self):
        for asset in self:
            active_rec = asset.assignment_ids.filtered(lambda a: a.state == 'assigned')
            asset.active_assignment_id = active_rec[:1] if active_rec else False

    @api.depends('assignment_ids', 'maintenance_ids')
    def _compute_counts(self):
        for asset in self:
            asset.assignment_count = len(asset.assignment_ids)
            asset.maintenance_count = len(asset.maintenance_ids)

    @api.depends('child_ids', 'accessory_ids')
    def _compute_bundle_counts(self):
        for asset in self:
            asset.child_count = len(asset.child_ids)
            asset.accessory_count = len(asset.accessory_ids)

    @api.depends('warranty_end_date')
    def _compute_warranty_status(self):
        today = fields.Date.today()
        for asset in self:
            if not asset.warranty_end_date:
                asset.warranty_status = 'none'
            elif asset.warranty_end_date < today:
                asset.warranty_status = 'expired'
            elif asset.warranty_end_date <= today + timedelta(days=30):
                asset.warranty_status = 'expiring'
            else:
                asset.warranty_status = 'valid'

    @api.depends('active_assignment_id.expected_return_date', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for asset in self:
            if asset.state == 'assigned' and asset.active_assignment_id and asset.active_assignment_id.expected_return_date:
                asset.is_overdue = bool(asset.active_assignment_id.expected_return_date < today)
            else:
                asset.is_overdue = False

    # --- Constraints ---
    @api.constrains('asset_code', 'company_id')
    def _check_unique_asset_code(self):
        for asset in self:
            if not asset.asset_code or not asset.asset_code.strip():
                raise ValidationError("Asset code cannot be empty!")
            domain = [('asset_code', '=ilike', asset.asset_code.strip()), ('id', '!=', asset.id)]
            if asset.company_id:
                domain.append(('company_id', '=', asset.company_id.id))
            if self.search_count(domain) > 0:
                raise ValidationError(f"Asset code '{asset.asset_code}' must be unique within the company!")

    @api.constrains('barcode', 'company_id')
    def _check_unique_barcode(self):
        for asset in self:
            if not asset.barcode or not asset.barcode.strip():
                continue
            domain = [('barcode', '=ilike', asset.barcode.strip()), ('id', '!=', asset.id)]
            if asset.company_id:
                domain.append(('company_id', '=', asset.company_id.id))
            if self.search_count(domain) > 0:
                raise ValidationError(f"Barcode '{asset.barcode}' must be unique within the company!")

    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        for asset in self:
            if asset.parent_id and asset.parent_id == asset:
                raise ValidationError("An asset cannot be its own parent bundle!")

    @api.constrains('serial_number', 'company_id')
    def _check_unique_serial_number(self):
        for asset in self:
            if not asset.serial_number or not asset.serial_number.strip():
                continue
            domain = [('serial_number', '=ilike', asset.serial_number.strip()), ('id', '!=', asset.id)]
            if asset.company_id:
                domain.append(('company_id', '=', asset.company_id.id))
            if self.search_count(domain) > 0:
                raise ValidationError(f"Serial number '{asset.serial_number}' must be unique within the company!")

    @api.constrains('purchase_price')
    def _check_purchase_price(self):
        for asset in self:
            if asset.purchase_price < 0:
                raise ValidationError("Purchase price cannot be negative!")

    @api.constrains('purchase_date', 'warranty_end_date')
    def _check_warranty_dates(self):
        for asset in self:
            if asset.purchase_date and asset.warranty_end_date and asset.warranty_end_date < asset.purchase_date:
                raise ValidationError("Warranty end date cannot be earlier than the purchase date!")

    @api.constrains('company_id', 'employee_id')
    def _check_company_consistency(self):
        for asset in self:
            if asset.employee_id and asset.company_id and asset.employee_id.company_id:
                if asset.employee_id.company_id != asset.company_id:
                    raise ValidationError(
                        f"Employee '{asset.employee_id.name}' belongs to company '{asset.employee_id.company_id.name}', "
                        f"which does not match asset company '{asset.company_id.name}'."
                    )

    @api.constrains('state', 'employee_id')
    def _check_state_employee_consistency(self):
        for asset in self:
            if asset.state in ('retired', 'lost') and asset.employee_id:
                raise ValidationError(f"Assets in '{asset.state}' state cannot remain assigned to an employee.")
            if asset.state == 'maintenance' and asset.employee_id:
                raise ValidationError("Assets under maintenance cannot be assigned to an employee.")
            if asset.state == 'assigned' and not asset.employee_id:
                raise ValidationError("Asset is marked as 'Assigned' but no employee is set.")
            if asset.state in ('draft', 'available') and asset.employee_id:
                raise ValidationError(f"Asset in '{asset.state}' state cannot have an assigned employee.")

    # --- Lifecycle Workflow Methods ---
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Auto-default barcode to asset_code if not supplied
            if not vals.get('barcode') and vals.get('asset_code'):
                vals['barcode'] = vals['asset_code']
        return super().create(vals_list)

    def action_set_to_available(self):
        for asset in self:
            if not asset.name or not asset.asset_code or not asset.category_id:
                raise UserError("Name, Asset Code, and Category are required before making an asset available.")
            if asset.state == 'assigned':
                raise UserError("Cannot mark an assigned asset as available directly. Please process its return.")
            if asset.state == 'maintenance':
                # Complete any ongoing maintenance records
                active_maints = self.env['employee.asset.maintenance'].search([
                    ('asset_id', '=', asset.id),
                    ('state', 'in', ('draft', 'scheduled', 'in_progress')),
                ])
                for m in active_maints:
                    m.write({
                        'state': 'completed',
                        'completion_date': m.completion_date or fields.Date.context_today(asset),
                        'resolution_notes': (m.resolution_notes or '') + f"\n[COMPLETED] Asset marked Available on {fields.Date.context_today(asset)}.",
                    })
            asset.write({'state': 'available'})
            asset.message_post(body="Asset marked as Available.")

    def action_assign_asset(self, employee, assigned_date=None, expected_return_date=None, condition_out=None, notes=None):
        """Programmatic and workflow method to assign an asset and bundled sub-assets to an employee."""
        self.ensure_one()
        if self.state != 'available':
            raise UserError(f"Only available assets can be assigned. Asset '{self.name}' is currently in '{self.state}' state.")
        if not employee:
            raise UserError("An eligible employee must be selected for assignment.")
        if employee.company_id and self.company_id and employee.company_id != self.company_id:
            raise ValidationError(
                f"Employee '{employee.name}' belongs to {employee.company_id.name}, which does not match asset company {self.company_id.name}."
            )
        # Check active assignment duplicate
        active = self.assignment_ids.filtered(lambda a: a.state == 'assigned')
        if active:
            raise UserError(f"Asset '{self.name}' already has an active assignment to '{active[0].employee_id.name}'.")

        # Create assignment record
        assignment = self.env['employee.asset.assignment'].create({
            'asset_id': self.id,
            'employee_id': employee.id,
            'assigned_date': assigned_date or fields.Date.context_today(self),
            'expected_return_date': expected_return_date,
            'assigned_by_id': self.env.user.id,
            'condition_out': condition_out or self.condition,
            'state': 'assigned',
            'company_id': self.company_id.id,
            'notes': notes,
        })

        # Update asset state
        self.write({
            'employee_id': employee.id,
            'state': 'assigned',
            'condition': condition_out or self.condition,
        })
        self.message_post(body=f"Asset assigned to {employee.name}.")

        # Auto-assign available bundled sub-assets
        for child in self.child_ids.filtered(lambda c: c.state == 'available'):
            child.action_assign_asset(
                employee=employee,
                assigned_date=assigned_date,
                expected_return_date=expected_return_date,
                condition_out=condition_out,
                notes=f"Auto-assigned as part of bundle {self.name}",
            )

        return assignment

    def action_open_assign_wizard(self):
        self.ensure_one()
        if self.state != 'available':
            raise UserError(f"Only available assets can be assigned. Asset '{self.name}' is in '{self.state}' state.")
        return {
            'name': f"Assign Asset: {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'asset.assign.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_asset_id': self.id,
                'default_condition_out': self.condition,
            },
        }

    def action_return_asset(self, returned_date=None, returned_to_id=None, condition_in=None, next_state='available', notes=None):
        """Programmatic and workflow method to return an asset and its bundled sub-assets."""
        self.ensure_one()
        if self.state != 'assigned':
            raise UserError(f"Asset '{self.name}' is not currently assigned (state is '{self.state}').")

        active_assignments = self.assignment_ids.filtered(lambda a: a.state == 'assigned')
        if not active_assignments:
            raise UserError(f"No active assignment record found for asset '{self.name}'.")

        assignment = active_assignments[0]
        ret_date = returned_date or fields.Date.context_today(self)
        receiver = returned_to_id or self.env.user
        ret_condition = condition_in or self.condition

        # Close assignment
        assignment.write({
            'returned_date': ret_date,
            'returned_to_id': receiver.id,
            'condition_in': ret_condition,
            'state': 'returned',
            'notes': (assignment.notes or '') + (f"\nReturn Remarks: {notes}" if notes else ''),
        })

        # Update asset
        next_asset_state = 'maintenance' if next_state == 'maintenance' or ret_condition == 'damaged' else 'available'
        self.write({
            'employee_id': False,
            'condition': ret_condition,
            'state': next_asset_state,
        })

        # Auto-create maintenance record if sent to maintenance
        if next_asset_state == 'maintenance':
            self.env['employee.asset.maintenance'].create({
                'name': f"Post-Return Maintenance for {self.name}",
                'asset_id': self.id,
                'maintenance_type': 'corrective',
                'description': notes or f"Asset returned by {assignment.employee_id.name} in '{ret_condition}' condition. Sent to maintenance upon return.",
                'reported_date': ret_date,
                'state': 'in_progress',
                'company_id': self.company_id.id,
            })

        self.message_post(body=f"Asset returned by {assignment.employee_id.name}. Condition: {ret_condition}. Next status: {next_asset_state}.")

        # Auto-return bundled sub-assets held by the same employee
        for child in self.child_ids.filtered(lambda c: c.state == 'assigned' and c.employee_id == assignment.employee_id):
            child.action_return_asset(
                returned_date=ret_date,
                returned_to_id=receiver,
                condition_in=ret_condition,
                next_state=next_state,
                notes=f"Auto-returned with bundle {self.name}",
            )

        return assignment

    def action_open_return_wizard(self):
        self.ensure_one()
        if self.state != 'assigned':
            raise UserError(f"Asset '{self.name}' is not currently assigned.")
        return {
            'name': f"Return Asset: {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'asset.return.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_asset_id': self.id,
                'default_assignment_id': self.active_assignment_id.id if self.active_assignment_id else False,
                'default_condition_in': self.condition,
            },
        }

    def action_send_to_maintenance(self):
        for asset in self:
            if asset.state == 'assigned' or asset.employee_id:
                raise UserError(f"Asset '{asset.name}' is currently assigned to {asset.employee_id.name}. Please process its return before placing it under maintenance.")
            if asset.state in ('retired', 'lost'):
                raise UserError(f"Cannot put a {asset.state} asset into maintenance.")
            asset.write({'state': 'maintenance'})
            maint = self.env['employee.asset.maintenance'].create({
                'name': f"Routine / Corrective Maintenance for {asset.name}",
                'asset_id': asset.id,
                'maintenance_type': 'corrective' if asset.condition == 'damaged' else 'preventive',
                'description': f"Asset '{asset.name}' sent to maintenance for inspection and servicing.",
                'reported_date': fields.Date.context_today(asset),
                'start_date': fields.Date.context_today(asset),
                'state': 'in_progress',
                'technician_id': self.env.user.id,
                'company_id': asset.company_id.id,
            })
            asset.message_post(body=f"Asset sent to Under Maintenance. Maintenance task '{maint.name}' created.")

    def action_retire_asset(self):
        for asset in self:
            if asset.state == 'assigned' or asset.employee_id:
                raise UserError(f"Asset '{asset.name}' is currently assigned. Please return the asset before retiring it.")
            asset.write({'state': 'retired'})
            asset.message_post(body="Asset has been retired from service.")

    def action_mark_lost(self):
        for asset in self:
            active = asset.assignment_ids.filtered(lambda a: a.state == 'assigned')
            if active:
                today = fields.Date.context_today(asset)
                for a in active:
                    a.write({
                        'returned_date': today,
                        'returned_to_id': self.env.user.id,
                        'state': 'cancelled',
                        'notes': (a.notes or '') + f"\n[AUDIT] Assignment closed: Asset marked as LOST on {today}.",
                    })
            asset.write({
                'employee_id': False,
                'state': 'lost',
            })
            asset.message_post(body="Asset marked as LOST.")

    def action_reset_to_draft(self):
        for asset in self:
            if asset.state == 'assigned':
                raise UserError("Cannot reset an assigned asset to Draft.")
            in_progress = self.env['employee.asset.maintenance'].search_count([
                ('asset_id', '=', asset.id),
                ('state', '=', 'in_progress'),
            ])
            if in_progress > 0:
                raise UserError("Cannot reset to Draft while maintenance tasks are in progress.")
            asset.write({'state': 'draft'})
            asset.message_post(body="Asset reset to Draft state.")

    def action_print_barcode_label(self):
        """Print barcode / QR sticker label for this asset."""
        self.ensure_one()
        return self.env.ref('employee_asset_tracker.action_report_asset_barcode').report_action(self)

    def action_view_assignments(self):
        self.ensure_one()
        return {
            'name': 'Assignments',
            'type': 'ir.actions.act_window',
            'res_model': 'employee.asset.assignment',
            'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
            'context': {'default_asset_id': self.id},
        }

    def action_view_maintenances(self):
        self.ensure_one()
        return {
            'name': 'Maintenance Records',
            'type': 'ir.actions.act_window',
            'res_model': 'employee.asset.maintenance',
            'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
            'context': {'default_asset_id': self.id, 'default_company_id': self.company_id.id},
        }

    def action_view_bundled_assets(self):
        self.ensure_one()
        return {
            'name': 'Bundled Sub-Assets',
            'type': 'ir.actions.act_window',
            'res_model': 'employee.asset',
            'view_mode': 'list,form',
            'domain': [('parent_id', '=', self.id)],
            'context': {'default_parent_id': self.id, 'default_company_id': self.company_id.id},
        }

    def action_open_bundle_wizard(self):
        """Open wizard to attach existing available inventory assets to this bundle."""
        self.ensure_one()
        if self.state in ('retired', 'lost'):
            raise UserError(f"Cannot attach sub-assets to a {self.state} bundle.")
        candidates = self.search([
            ('id', '!=', self.id),
            ('state', '=', 'available'),
            ('parent_id', '=', False),
            ('company_id', '=', self.company_id.id),
        ])
        if not candidates:
            raise UserError(f"No available standalone assets found in inventory for '{self.company_id.name}' to attach to this bundle.")

        wizard = self.env['asset.bundle.wizard'].create({
            'parent_asset_id': self.id,
            'line_ids': [
                (0, 0, {
                    'asset_id': asset.id,
                    'selected': False,
                }) for asset in candidates
            ],
        })

        return {
            'name': f"Attach Existing Assets to {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'asset.bundle.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_parent_asset_id': self.id,
            },
        }

    def action_remove_from_bundle(self):
        """Detach this asset from its parent bundle and return to standalone stock."""
        for asset in self:
            parent = asset.parent_id
            if not parent:
                continue
            if parent.state == 'assigned':
                raise UserError("Cannot detach sub-assets while the bundle is actively assigned. Return the bundle first.")
            asset.parent_id = False
            parent.message_post(
                body=f"Asset <b>{asset.name}</b> ({asset.asset_code}) was removed from this bundle."
            )
            asset.message_post(
                body=f"Asset was removed from bundle <b>{parent.name}</b> ({parent.asset_code})."
            )
        return True

    def action_view_accessories(self):
        self.ensure_one()
        return {
            'name': 'Accessories & Peripherals',
            'type': 'ir.actions.act_window',
            'res_model': 'employee.asset.accessory',
            'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
            'context': {'default_asset_id': self.id, 'default_company_id': self.company_id.id},
        }

    @api.model
    def _cron_check_warranty_expiry(self):
        """Daily scheduled action to alert managers of assets with warranties expiring in next 30 days."""
        today = fields.Date.today()
        target_date = today + timedelta(days=30)
        expiring_assets = self.search([
            ('warranty_end_date', '>=', today),
            ('warranty_end_date', '<=', target_date),
            ('state', 'not in', ('retired', 'lost')),
        ])
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for asset in expiring_assets:
            existing = self.env['mail.activity'].search_count([
                ('res_id', '=', asset.id),
                ('res_model', '=', 'employee.asset'),
                ('summary', 'ilike', 'Warranty Expiry Warning'),
            ])
            if not existing and activity_type:
                target_user = self.env.ref('base.user_admin', raise_if_not_found=False)
                if target_user:
                    asset.activity_schedule(
                        activity_type_id=activity_type.id,
                        date_deadline=asset.warranty_end_date,
                        summary=f"Warranty Expiry Warning: {asset.name}",
                        note=f"The warranty for asset '{asset.name}' ({asset.asset_code}) will expire on {asset.warranty_end_date}.",
                        user_id=target_user.id,
                    )
                    asset.message_post(
                        body=f"⚠️ <b>Warranty Alert:</b> Warranty will expire on {asset.warranty_end_date} (within 30 days)."
                    )

    def unlink(self):
        for asset in self:
            if asset.state == 'assigned':
                raise UserError(f"Cannot delete asset '{asset.name}' while it is assigned to an employee.")
            if asset.state == 'maintenance':
                raise UserError(f"Cannot delete asset '{asset.name}' while it is under maintenance.")
        return super().unlink()

    @api.model
    def get_dashboard_metrics(self):
        """Aggregate real-time KPI metrics, category breakdowns, and actionable task queues for the OWL dashboard."""
        company = self.env.company
        today = fields.Date.today()
        currency_symbol = company.currency_id.symbol or '$'

        assets = self.search([('company_id', '=', company.id)])

        total_assets = len(assets)
        available_assets = len(assets.filtered(lambda a: a.state == 'available'))
        assigned_assets = len(assets.filtered(lambda a: a.state == 'assigned'))
        maintenance_assets = len(assets.filtered(lambda a: a.state == 'maintenance'))
        retired_assets = len(assets.filtered(lambda a: a.state == 'retired'))
        lost_assets = len(assets.filtered(lambda a: a.state == 'lost'))

        active_pool = available_assets + assigned_assets
        utilization_rate = round((assigned_assets / active_pool * 100), 1) if active_pool > 0 else 0.0

        valuation_sum = sum(assets.filtered(lambda a: a.state not in ('retired', 'lost')).mapped('purchase_price'))
        total_valuation = f"{currency_symbol}{valuation_sum:,.2f}"

        # Overdue assignments
        overdue_assignments = self.env['employee.asset.assignment'].search([
            ('company_id', '=', company.id),
            ('is_overdue', '=', True),
        ], order='expected_return_date asc')
        overdue_count = len(overdue_assignments)

        # Warranty expiring within 30 days
        warranty_expiring_assets = assets.filtered(lambda a: a.warranty_status == 'expiring')
        warranty_expiring_count = len(warranty_expiring_assets)

        # Category breakdown
        categories = self.env['employee.asset.category'].search([('company_id', '=', company.id)])
        category_data = []
        for cat in categories:
            cat_count = len(assets.filtered(lambda a: a.category_id == cat))
            if cat_count > 0:
                pct = round((cat_count / total_assets * 100), 1) if total_assets > 0 else 0.0
                category_data.append({
                    'id': cat.id,
                    'name': cat.name,
                    'code': cat.code or '',
                    'count': cat_count,
                    'percentage': pct,
                })
        category_data.sort(key=lambda c: c['count'], reverse=True)

        # Department breakdown for assigned assets
        dept_counts = {}
        for a in assets.filtered(lambda x: x.state == 'assigned' and x.department_id):
            dept_name = a.department_id.name
            dept_counts[dept_name] = dept_counts.get(dept_name, 0) + 1
        department_data = [
            {'name': k, 'count': v, 'percentage': round(v / assigned_assets * 100, 1) if assigned_assets > 0 else 0.0}
            for k, v in sorted(dept_counts.items(), key=lambda item: item[1], reverse=True)[:5]
        ]

        # Urgent Overdue Queue (top 5)
        urgent_overdue_list = []
        for o in overdue_assignments[:5]:
            days = (today - o.expected_return_date).days if o.expected_return_date else 0
            urgent_overdue_list.append({
                'assignment_id': o.id,
                'asset_id': o.asset_id.id,
                'asset_name': o.asset_id.name,
                'asset_code': o.asset_id.asset_code,
                'employee_name': o.employee_id.name,
                'expected_return_date': o.expected_return_date.strftime('%Y-%m-%d') if o.expected_return_date else '',
                'days_overdue': days,
            })

        # Recent Allocations (top 5)
        recent_allocations = self.env['employee.asset.assignment'].search(
            [('company_id', '=', company.id)],
            order='assigned_date desc, id desc',
            limit=5
        )
        recent_allocations_list = []
        for r in recent_allocations:
            recent_allocations_list.append({
                'assignment_id': r.id,
                'asset_id': r.asset_id.id,
                'asset_name': r.asset_id.name,
                'asset_code': r.asset_id.asset_code,
                'employee_name': r.employee_id.name,
                'assigned_date': r.assigned_date.strftime('%Y-%m-%d') if r.assigned_date else '',
                'condition_out': r.condition_out,
                'state': r.state,
            })

        # Maintenance Tasks (in_progress, scheduled)
        active_maintenances = self.env['employee.asset.maintenance'].search(
            [('company_id', '=', company.id), ('state', 'in', ('scheduled', 'in_progress'))],
            order='reported_date desc',
            limit=5
        )
        maintenance_list = []
        for m in active_maintenances:
            maintenance_list.append({
                'id': m.id,
                'name': m.name,
                'asset_name': m.asset_id.name,
                'maintenance_type': m.maintenance_type,
                'state': m.state,
                'technician_name': m.technician_id.name if m.technician_id else 'Unassigned',
                'cost': f"{currency_symbol}{m.cost:,.2f}" if m.cost else f"{currency_symbol}0.00",
            })

        # Warranty Expiring Soon (top 5)
        warranty_list = []
        for w in warranty_expiring_assets[:5]:
            days_left = (w.warranty_end_date - today).days if w.warranty_end_date else 0
            warranty_list.append({
                'id': w.id,
                'name': w.name,
                'asset_code': w.asset_code,
                'warranty_end_date': w.warranty_end_date.strftime('%Y-%m-%d') if w.warranty_end_date else '',
                'days_left': max(0, days_left),
            })

        return {
            'company_name': company.name,
            'currency_symbol': currency_symbol,
            'total_assets': total_assets,
            'available_assets': available_assets,
            'assigned_assets': assigned_assets,
            'utilization_rate': utilization_rate,
            'maintenance_assets': maintenance_assets,
            'retired_assets': retired_assets,
            'lost_assets': lost_assets,
            'overdue_count': overdue_count,
            'warranty_expiring_count': warranty_expiring_count,
            'total_valuation': total_valuation,
            'categories': category_data,
            'departments': department_data,
            'urgent_overdue': urgent_overdue_list,
            'recent_allocations': recent_allocations_list,
            'maintenances': maintenance_list,
            'warranty_expiring': warranty_list,
        }

