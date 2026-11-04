# -*- coding: utf-8 -*-

from odoo import fields, models


class EmployeeAssetAccessory(models.Model):
    _name = 'employee.asset.accessory'
    _description = 'Asset Peripheral & Accessory'
    _order = 'accessory_type, name'

    name = fields.Char(string='Accessory Name', required=True)
    asset_id = fields.Many2one(
        'employee.asset',
        string='Main Asset',
        required=True,
        ondelete='cascade',
        index=True
    )
    accessory_type = fields.Selection(
        [
            ('charger', 'Power Adapter / Charger'),
            ('cable', 'Cable / Converter'),
            ('dock', 'Docking Station / Hub'),
            ('peripherals', 'Mouse / Keyboard'),
            ('case', 'Bag / Protective Sleeve'),
            ('other', 'Other Peripheral'),
        ],
        string='Type',
        default='other',
        required=True
    )
    serial_number = fields.Char(string='Serial / Part Number')
    condition = fields.Selection(
        [
            ('new', 'New'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('damaged', 'Damaged'),
        ],
        string='Condition',
        default='good',
        required=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='asset_id.company_id',
        store=True,
        readonly=True
    )
    notes = fields.Text(string='Remarks')
