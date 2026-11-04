# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EmployeeAssetCategory(models.Model):
    _name = 'employee.asset.category'
    _description = 'Asset Category'
    _order = 'name'

    name = fields.Char(string='Category Name', required=True, translate=True)
    code = fields.Char(string='Code', copy=False, help='Unique short reference code for the category')
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        help='Company restriction if category is company-specific'
    )
    asset_ids = fields.One2many(
        'employee.asset',
        'category_id',
        string='Assets'
    )
    asset_count = fields.Integer(
        string='Asset Count',
        compute='_compute_asset_count',
        store=False
    )

    @api.depends('asset_ids')
    def _compute_asset_count(self):
        for record in self:
            record.asset_count = len(record.asset_ids)

    @api.constrains('code', 'company_id')
    def _check_unique_code(self):
        for record in self:
            if not record.code or not record.code.strip():
                continue
            domain = [('code', '=ilike', record.code.strip()), ('id', '!=', record.id)]
            if record.company_id:
                domain.append(('company_id', '=', record.company_id.id))
            if self.search_count(domain) > 0:
                raise ValidationError(f"Category code '{record.code}' must be unique within the company!")

    def unlink(self):
        for category in self:
            if category.asset_ids:
                raise UserError(
                    f"Cannot delete category '{category.name}' because it contains {len(category.asset_ids)} linked asset(s). "
                    "Please reassign or delete the linked assets first, or archive this category."
                )
        return super().unlink()

    def action_view_assets(self):
        self.ensure_one()
        return {
            'name': f"Assets - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'employee.asset',
            'view_mode': 'list,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id},
        }
