# -*- coding: utf-8 -*-
{
    'name': 'Employee Asset Tracker',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Manage employee assets, assignments, returns, and maintenance.',
    'description': """
Employee Asset Tracker
======================
Comprehensive management of company equipment and employee asset allocation:
- Asset registration with serial and warranty tracking
- Allocation and return history with condition monitoring
- Preventive and corrective maintenance scheduling
- Multi-company awareness and role-based access control
- Complete auditability with chatter integration
- HR Employee form integration with asset counts and dedicated offboarding tab
- Accessories and bundling hierarchy
- Automated alerts for overdue returns and warranty expiry
- Barcode / QR Code generation and quick-scan lookup
    """,
    'author': 'Custom Development',
    'website': 'https://www.odoo.com',
    'license': 'LGPL-3',
    'depends': ['hr', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'report/asset_barcode_report.xml',
        'wizard/asset_assign_wizard_views.xml',
        'wizard/asset_return_wizard_views.xml',
        'wizard/asset_scan_wizard_views.xml',
        'wizard/asset_bundle_wizard_views.xml',
        'views/employee_asset_views.xml',
        'views/asset_category_views.xml',
        'views/asset_assignment_views.xml',
        'views/asset_maintenance_views.xml',
        'views/hr_employee_views.xml',
        'views/employee_asset_menus.xml',
    ],
    'demo': [
        'demo/employee_asset_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'employee_asset_tracker/static/src/**/*',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
