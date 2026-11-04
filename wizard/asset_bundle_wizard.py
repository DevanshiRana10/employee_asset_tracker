# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class AssetBundleWizard(models.TransientModel):
    _name = 'asset.bundle.wizard'
    _description = 'Attach Existing Assets to Bundle'

    parent_asset_id = fields.Many2one(
        'employee.asset',
        string='Parent Bundle',
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='parent_asset_id.company_id',
        readonly=True,
    )
    line_ids = fields.One2many(
        'asset.bundle.wizard.line',
        'wizard_id',
        string='Available Assets in Stock',
    )
    selected_count = fields.Integer(
        string='Selected Count',
        compute='_compute_selected_count',
    )
    selected_count_text = fields.Char(
        string='Selection Status',
        compute='_compute_selected_count',
    )
    # Kept for direct programmatic/API access and test backwards compatibility
    asset_ids = fields.Many2many(
        'employee.asset',
        'asset_bundle_wizard_rel',
        'wizard_id',
        'asset_id',
        string='Assets to Attach',
        domain="[('id', '!=', parent_asset_id), ('state', '=', 'available'), ('parent_id', '=', False), ('company_id', '=', company_id)]",
    )

    @api.depends('line_ids.selected', 'asset_ids')
    def _compute_selected_count(self):
        for wizard in self:
            count = len(wizard.line_ids.filtered('selected')) + len(wizard.asset_ids)
            wizard.selected_count = count
            wizard.selected_count_text = f"{count} asset(s) selected" if count else "No assets selected"

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        parent_id = res.get('parent_asset_id') or self.env.context.get('default_parent_asset_id')
        if parent_id:
            parent = self.env['employee.asset'].browse(parent_id)
            candidates = self.env['employee.asset'].search([
                ('id', '!=', parent.id),
                ('state', '=', 'available'),
                ('parent_id', '=', False),
                ('company_id', '=', parent.company_id.id),
            ])
            lines = []
            for asset in candidates:
                lines.append((0, 0, {
                    'asset_id': asset.id,
                    'selected': False,
                }))
            res['line_ids'] = lines
        return res

    def action_select_all(self):
        self.ensure_one()
        for line in self.line_ids:
            line.selected = True
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'asset.bundle.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_deselect_all(self):
        self.ensure_one()
        for line in self.line_ids:
            line.selected = False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'asset.bundle.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_confirm(self):
        self.ensure_one()
        if not self.parent_asset_id:
            raise UserError("Parent bundle asset is required.")
        if self.parent_asset_id.state in ('retired', 'lost'):
            raise UserError(f"Cannot add sub-assets to a {self.parent_asset_id.state} bundle.")

        # Combine items selected via wizard lines or asset_ids
        selected_from_lines = self.line_ids.filtered('selected').mapped('asset_id')
        assets_to_attach = selected_from_lines | self.asset_ids

        if not assets_to_attach:
            raise UserError("Please select at least one asset to attach to the bundle.")

        parent = self.parent_asset_id

        for asset in assets_to_attach:
            if asset.id == parent.id:
                raise ValidationError(f"Asset '{asset.name}' cannot be bundled into itself.")
            if asset.state != 'available':
                raise ValidationError(f"Asset '{asset.name}' must be in 'available' state to be bundled (currently '{asset.state}').")
            if asset.parent_id:
                raise ValidationError(f"Asset '{asset.name}' already belongs to bundle '{asset.parent_id.name}'.")
            if asset.company_id != parent.company_id:
                raise ValidationError(
                    f"Asset '{asset.name}' belongs to company '{asset.company_id.name}', which differs from bundle company '{parent.company_id.name}'."
                )

        for asset in assets_to_attach:
            asset.write({'parent_id': parent.id})

            # If parent bundle is actively assigned, cascade assignment to newly attached sub-asset
            if parent.state == 'assigned' and parent.employee_id:
                asset.action_assign_asset(
                    employee=parent.employee_id,
                    condition_out=asset.condition,
                    notes=f"Auto-assigned upon joining active bundle '{parent.name}'",
                )

            # Audit logging in chatter
            parent.message_post(
                body=f"Asset <b>{asset.name}</b> ({asset.asset_code}) was added to bundle <b>{parent.name}</b>."
            )
            asset.message_post(
                body=f"Asset was added to bundle <b>{parent.name}</b> ({parent.asset_code})."
            )

        return {'type': 'ir.actions.act_window_close'}


class AssetBundleWizardLine(models.TransientModel):
    _name = 'asset.bundle.wizard.line'
    _description = 'Available Asset Candidate Line'

    wizard_id = fields.Many2one(
        'asset.bundle.wizard',
        string='Wizard',
        ondelete='cascade',
        required=True,
    )
    selected = fields.Boolean(
        string='Select',
        default=False,
    )
    asset_id = fields.Many2one(
        'employee.asset',
        string='Asset',
    )
    asset_code = fields.Char(related='asset_id.asset_code', readonly=True)
    name = fields.Char(related='asset_id.name', readonly=True)
    category_id = fields.Many2one(related='asset_id.category_id', readonly=True)
    serial_number = fields.Char(related='asset_id.serial_number', readonly=True)
    barcode = fields.Char(related='asset_id.barcode', readonly=True)
    condition = fields.Selection(related='asset_id.condition', readonly=True)
