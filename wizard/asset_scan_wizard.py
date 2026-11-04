# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.exceptions import UserError


class AssetScanWizard(models.TransientModel):
    _name = 'asset.scan.wizard'
    _description = 'Scan Asset Tag / Quick Action Wizard'

    search_code = fields.Char(
        string='Scan Barcode / QR / Tag',
        help='Scan barcode with USB/Bluetooth scanner or enter Asset Code / Serial Number',
    )
    asset_id = fields.Many2one(
        'employee.asset',
        string='Identified Asset',
        readonly=True
    )
    asset_name = fields.Char(related='asset_id.name', string='Asset Name', readonly=True)
    asset_state = fields.Selection(related='asset_id.state', string='Status', readonly=True)
    asset_employee_id = fields.Many2one(related='asset_id.employee_id', string='Current Employee', readonly=True)
    asset_condition = fields.Selection(related='asset_id.condition', string='Condition', readonly=True)
    asset_location = fields.Char(related='asset_id.location', string='Location', readonly=True)

    def action_lookup_asset(self):
        """Find asset by barcode, asset_code, or serial_number."""
        self.ensure_one()
        query = (self.search_code or '').strip()
        if not query:
            raise UserError("Please scan or enter a barcode/tag.")

        asset = self.env['employee.asset'].search([
            '|', '|',
            ('barcode', '=ilike', query),
            ('asset_code', '=ilike', query),
            ('serial_number', '=ilike', query),
        ], limit=1)

        if not asset:
            raise UserError(f"No asset found matching barcode/tag: '{query}'")

        self.asset_id = asset.id
        # Re-render wizard with identified asset
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'asset.scan.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_open_asset(self):
        self.ensure_one()
        if not self.asset_id:
            raise UserError("Please scan or find an asset first.")
        return {
            'name': self.asset_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'employee.asset',
            'res_id': self.asset_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_quick_assign(self):
        self.ensure_one()
        if not self.asset_id:
            raise UserError("Please scan an asset first.")
        return self.asset_id.action_open_assign_wizard()

    def action_quick_return(self):
        self.ensure_one()
        if not self.asset_id:
            raise UserError("Please scan an asset first.")
        return self.asset_id.action_open_return_wizard()
