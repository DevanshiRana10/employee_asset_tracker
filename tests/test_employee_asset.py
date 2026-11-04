# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo import fields
from datetime import timedelta


@tagged('post_install', '-at_install', 'employee_asset')
class TestEmployeeAsset(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_1 = cls.env.company
        cls.company_2 = cls.env['res.company'].create({
            'name': 'Second Test Company',
            'currency_id': cls.company_1.currency_id.id,
        })

        # Category
        cls.category_laptop = cls.env['employee.asset.category'].create({
            'name': 'Test Laptops',
            'code': 'TEST-LAP-01',
            'company_id': cls.company_1.id,
        })

        # Employees
        cls.employee_1 = cls.env['hr.employee'].create({
            'name': 'Alice Johnson',
            'company_id': cls.company_1.id,
        })
        cls.employee_2 = cls.env['hr.employee'].create({
            'name': 'Bob Smith',
            'company_id': cls.company_1.id,
        })
        cls.employee_foreign = cls.env['hr.employee'].create({
            'name': 'Charlie External',
            'company_id': cls.company_2.id,
        })

        # Users
        cls.user_asset_officer = cls.env['res.users'].create({
            'name': 'Asset Officer',
            'login': 'test_asset_officer_01',
            'email': 'officer_test@example.com',
            'company_id': cls.company_1.id,
            'company_ids': [(6, 0, [cls.company_1.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.env.ref('employee_asset_tracker.group_employee_asset_user').id])],
        })

    def test_01_create_asset_valid_values(self):
        """1. Creating an asset with valid values."""
        today = fields.Date.today()
        asset = self.env['employee.asset'].create({
            'name': 'MacBook Pro 16',
            'asset_code': 'AST-TEST-001',
            'serial_number': 'SN-MBP-001',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
            'purchase_date': today - timedelta(days=30),
            'warranty_end_date': today + timedelta(days=365),
            'purchase_price': 2499.00,
            'state': 'draft',
        })
        self.assertEqual(asset.name, 'MacBook Pro 16')
        self.assertEqual(asset.purchase_price, 2499.00)
        self.assertEqual(asset.currency_id, self.company_1.currency_id)
        # Advance to available
        asset.action_set_to_available()
        self.assertEqual(asset.state, 'available')

    def test_02_reject_duplicate_asset_code(self):
        """2. Rejecting duplicate asset codes within the company."""
        self.env['employee.asset'].create({
            'name': 'Dell XPS 15',
            'asset_code': 'AST-UNIQUE-CODE',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        with self.assertRaises(ValidationError):
            self.env['employee.asset'].create({
                'name': 'Duplicate Code Laptop',
                'asset_code': 'AST-UNIQUE-CODE',
                'category_id': self.category_laptop.id,
                'company_id': self.company_1.id,
            })

    def test_03_reject_duplicate_serial_number(self):
        """3. Rejecting duplicate serial numbers when applicable."""
        self.env['employee.asset'].create({
            'name': 'Lenovo ThinkPad X1',
            'asset_code': 'AST-SN-001',
            'serial_number': 'SN-DUPLICATE-CHECK',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        with self.assertRaises(ValidationError):
            self.env['employee.asset'].create({
                'name': 'Another ThinkPad',
                'asset_code': 'AST-SN-002',
                'serial_number': 'SN-DUPLICATE-CHECK',
                'category_id': self.category_laptop.id,
                'company_id': self.company_1.id,
            })

    def test_04_reject_negative_purchase_price(self):
        """4. Rejecting negative purchase prices."""
        with self.assertRaises(ValidationError):
            self.env['employee.asset'].create({
                'name': 'Invalid Price Asset',
                'asset_code': 'AST-NEG-PRICE',
                'category_id': self.category_laptop.id,
                'company_id': self.company_1.id,
                'purchase_price': -150.0,
            })

    def test_05_reject_invalid_warranty_dates(self):
        """5. Rejecting invalid warranty dates (end before purchase)."""
        today = fields.Date.today()
        with self.assertRaises(ValidationError):
            self.env['employee.asset'].create({
                'name': 'Invalid Warranty Asset',
                'asset_code': 'AST-BAD-DATES',
                'category_id': self.category_laptop.id,
                'company_id': self.company_1.id,
                'purchase_date': today,
                'warranty_end_date': today - timedelta(days=10),
            })

    def test_06_assign_available_asset_successfully(self):
        """6. Assigning an available asset successfully."""
        asset = self.env['employee.asset'].create({
            'name': 'MacBook Air M2',
            'asset_code': 'AST-ASSIGN-01',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        asset.action_set_to_available()
        self.assertEqual(asset.state, 'available')

        assignment = asset.action_assign_asset(
            employee=self.employee_1,
            assigned_date=fields.Date.today(),
            condition_out='new',
            notes='Initial assignment test',
        )
        self.assertEqual(asset.state, 'assigned')
        self.assertEqual(asset.employee_id.id, self.employee_1.id)
        self.assertEqual(asset.active_assignment_id.id, assignment.id)
        self.assertEqual(assignment.state, 'assigned')
        self.assertEqual(assignment.condition_out, 'new')

    def test_07_reject_assignment_of_already_assigned_asset(self):
        """7. Rejecting assignment of an already assigned asset."""
        asset = self.env['employee.asset'].create({
            'name': 'MacBook Pro 14',
            'asset_code': 'AST-DBL-ASSIGN',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        asset.action_set_to_available()
        asset.action_assign_asset(employee=self.employee_1)

        # Attempt to assign again while already assigned
        with self.assertRaises(UserError):
            asset.action_assign_asset(employee=self.employee_2)

    def test_08_reject_assignment_of_ineligible_assets(self):
        """8. Rejecting assignment of retired, lost, or under-maintenance assets."""
        asset = self.env['employee.asset'].create({
            'name': 'Asus ZenBook',
            'asset_code': 'AST-INELIGIBLE',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        # Draft cannot be assigned directly
        with self.assertRaises(UserError):
            asset.action_assign_asset(employee=self.employee_1)

        # Maintenance cannot be assigned
        asset.action_send_to_maintenance()
        self.assertEqual(asset.state, 'maintenance')
        with self.assertRaises(UserError):
            asset.action_assign_asset(employee=self.employee_1)

        # Retired cannot be assigned
        asset.action_set_to_available()
        asset.action_retire_asset()
        self.assertEqual(asset.state, 'retired')
        with self.assertRaises(UserError):
            asset.action_assign_asset(employee=self.employee_1)

    def test_09_and_10_return_assigned_asset_and_preserve_history(self):
        """9 & 10. Returning an assigned asset successfully and preserving history."""
        asset = self.env['employee.asset'].create({
            'name': 'HP EliteBook 840',
            'asset_code': 'AST-RET-01',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        asset.action_set_to_available()
        assignment = asset.action_assign_asset(employee=self.employee_1)

        # Return asset
        ret_date = fields.Date.today()
        asset.action_return_asset(
            returned_date=ret_date,
            condition_in='good',
            next_state='available',
            notes='All accessories returned intact.',
        )
        self.assertEqual(asset.state, 'available')
        self.assertFalse(asset.employee_id)
        self.assertFalse(asset.active_assignment_id)
        # Verify history preservation
        self.assertEqual(len(asset.assignment_ids), 1)
        self.assertEqual(assignment.state, 'returned')
        self.assertEqual(assignment.condition_in, 'good')
        self.assertEqual(assignment.returned_date, ret_date)

    def test_11_reject_duplicate_return(self):
        """11. Rejecting a duplicate return."""
        asset = self.env['employee.asset'].create({
            'name': 'Surface Laptop 5',
            'asset_code': 'AST-DUP-RET',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        asset.action_set_to_available()
        asset.action_assign_asset(employee=self.employee_1)
        asset.action_return_asset()

        # Attempt to return again
        with self.assertRaises(UserError):
            asset.action_return_asset()

    def test_12_starting_and_completing_maintenance(self):
        """12. Starting and completing maintenance workflow."""
        asset = self.env['employee.asset'].create({
            'name': 'Mac Mini M2',
            'asset_code': 'AST-MAINT-01',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        asset.action_set_to_available()

        maint = self.env['employee.asset.maintenance'].create({
            'name': 'RAM Upgrade',
            'asset_id': asset.id,
            'maintenance_type': 'corrective',
            'description': 'Upgrade RAM to 32GB',
            'cost': 120.0,
            'company_id': self.company_1.id,
        })
        self.assertEqual(maint.state, 'draft')

        # Schedule
        maint.action_schedule()
        self.assertEqual(maint.state, 'scheduled')

        # Start
        maint.action_start()
        self.assertEqual(maint.state, 'in_progress')
        self.assertEqual(asset.state, 'maintenance')

        # Complete
        maint.action_complete()
        self.assertEqual(maint.state, 'completed')
        self.assertEqual(asset.state, 'available')

    def test_13_prevent_maintenance_completion_restoring_retired_or_lost_asset(self):
        """13. Preventing maintenance completion from incorrectly restoring a retired/lost asset."""
        asset = self.env['employee.asset'].create({
            'name': 'Old iMac',
            'asset_code': 'AST-RET-MAINT',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        maint = self.env['employee.asset.maintenance'].create({
            'name': 'Final Data Wipe',
            'asset_id': asset.id,
            'maintenance_type': 'preventive',
            'description': 'Securely wipe SSD before recycling',
            'company_id': self.company_1.id,
        })
        maint.action_start()
        # Admin marks asset as retired during/after decommissioning
        asset.write({'state': 'retired'})

        # Complete maintenance
        maint.action_complete()
        # Asset must remain retired, not restored to available!
        self.assertEqual(asset.state, 'retired')

    def test_14_prevent_invalid_state_transitions(self):
        """14. Preventing invalid state transitions."""
        asset = self.env['employee.asset'].create({
            'name': 'Test Laptop Transitions',
            'asset_code': 'AST-TRANS-01',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        asset.action_set_to_available()
        asset.action_assign_asset(employee=self.employee_1)

        # Cannot retire directly while assigned
        with self.assertRaises(UserError):
            asset.action_retire_asset()

        # Cannot put in maintenance while assigned without returning
        with self.assertRaises(UserError):
            asset.action_send_to_maintenance()

    def test_15_permissions_and_company_consistency(self):
        """15. Verifying user permissions and company consistency."""
        # Reject assignment of employee from a different company
        asset = self.env['employee.asset'].create({
            'name': 'Company 1 Asset',
            'asset_code': 'AST-COMP-01',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        asset.action_set_to_available()

        with self.assertRaises(ValidationError):
            asset.action_assign_asset(employee=self.foreign_employee if hasattr(self, 'foreign_employee') else self.employee_foreign)

        # Category deletion protection
        with self.assertRaises(UserError):
            self.category_laptop.unlink()

    def test_16_hr_employee_asset_integration(self):
        """16. HR Employee Form integration: asset count, assigned_asset_ids, and action view."""
        asset = self.env['employee.asset'].create({
            'name': 'ThinkPad T14 Gen 4',
            'asset_code': 'AST-HR-TEST-01',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        asset.action_set_to_available()

        # Alice initially has 0 assets
        self.assertEqual(self.employee_1.asset_count, 0)
        self.assertNotIn(asset, self.employee_1.assigned_asset_ids)

        # Assign asset to Alice
        asset.action_assign_asset(employee=self.employee_1)
        self.assertEqual(self.employee_1.asset_count, 1)
        self.assertIn(asset, self.employee_1.assigned_asset_ids)

        # Test smart button action
        action = self.employee_1.action_view_assigned_assets()
        self.assertEqual(action['res_model'], 'employee.asset')
        self.assertIn(('employee_id', '=', self.employee_1.id), action['domain'])

        # Return asset
        asset.action_return_asset()
        self.assertEqual(self.employee_1.asset_count, 0)
        self.assertNotIn(asset, self.employee_1.assigned_asset_ids)

    def test_17_accessories_and_bundling(self):
        """17. Accessories & Bundling: sub-assets cascade assignment/return, accessories tracked."""
        parent_asset = self.env['employee.asset'].create({
            'name': 'Mac Studio M2 Max',
            'asset_code': 'AST-BUNDLE-PC',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        child_monitor = self.env['employee.asset'].create({
            'name': 'Studio Display 27-inch',
            'asset_code': 'AST-BUNDLE-MON',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
            'parent_id': parent_asset.id,
        })
        # Add accessories
        self.env['employee.asset.accessory'].create([
            {
                'name': 'Power Cable',
                'asset_id': parent_asset.id,
                'accessory_type': 'charger',
                'company_id': self.company_1.id,
            },
            {
                'name': 'Thunderbolt 4 Cable',
                'asset_id': parent_asset.id,
                'accessory_type': 'cable',
                'company_id': self.company_1.id,
            },
        ])

        self.assertEqual(parent_asset.child_count, 1)
        self.assertEqual(parent_asset.accessory_count, 2)

        parent_asset.action_set_to_available()
        child_monitor.action_set_to_available()

        # Assign parent bundle to Bob
        parent_asset.action_assign_asset(employee=self.employee_2)
        self.assertEqual(parent_asset.state, 'assigned')
        self.assertEqual(parent_asset.employee_id.id, self.employee_2.id)

        # Child monitor should automatically cascade to assigned
        self.assertEqual(child_monitor.state, 'assigned')
        self.assertEqual(child_monitor.employee_id.id, self.employee_2.id)

        # Return parent bundle
        parent_asset.action_return_asset()
        self.assertEqual(parent_asset.state, 'available')
        self.assertFalse(parent_asset.employee_id)
        # Child monitor cascades back to available
        self.assertEqual(child_monitor.state, 'available')
        self.assertFalse(child_monitor.employee_id)

    def test_18_overdue_and_warranty_alerts(self):
        """18. Automated overdue checks and warranty expiry notifications."""
        today = fields.Date.today()
        # Expiring warranty asset
        asset_expiring = self.env['employee.asset'].create({
            'name': 'Dell Precision 5570',
            'asset_code': 'AST-WARR-EXP',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
            'warranty_end_date': today + timedelta(days=15),
        })
        self.assertEqual(asset_expiring.warranty_status, 'expiring')

        # Run cron for warranty check
        self.env['employee.asset']._cron_check_warranty_expiry()

        # Overdue assignment asset
        asset_overdue = self.env['employee.asset'].create({
            'name': 'iPad Pro 12.9',
            'asset_code': 'AST-OVERDUE-01',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        asset_overdue.action_set_to_available()
        assignment = asset_overdue.action_assign_asset(
            employee=self.employee_1,
            assigned_date=today - timedelta(days=10),
            expected_return_date=today - timedelta(days=2),
        )
        self.assertTrue(assignment.is_overdue)
        self.assertTrue(asset_overdue.is_overdue)

        # Run cron for overdue check
        self.env['employee.asset.assignment']._cron_check_overdue_assignments()

    def test_19_barcode_generation_and_scan_wizard(self):
        """19. Barcode auto-generation, report action, and scan lookup wizard."""
        asset = self.env['employee.asset'].create({
            'name': 'Logitech MX Master 3S',
            'asset_code': 'AST-SCAN-01',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        # Default barcode is set to asset_code
        self.assertEqual(asset.barcode, 'AST-SCAN-01')

        # Print label action returns report
        report_action = asset.action_print_barcode_label()
        self.assertEqual(report_action['type'], 'ir.actions.report')
        self.assertEqual(report_action['report_name'], 'employee_asset_tracker.report_asset_barcode_template')

        # Scan wizard lookup by barcode
        wizard = self.env['asset.scan.wizard'].create({
            'search_code': 'AST-SCAN-01',
        })
        wizard.action_lookup_asset()
        self.assertEqual(wizard.asset_id.id, asset.id)

        # Scan wizard lookup with invalid barcode raises UserError
        wizard_bad = self.env['asset.scan.wizard'].create({
            'search_code': 'DOES-NOT-EXIST-999',
        })
        with self.assertRaises(UserError):
            wizard_bad.action_lookup_asset()

    def test_20_bundle_wizard_attach_and_detach(self):
        """20. Enterprise Bundling: attach existing assets via wizard, prevent invalid company/assigned assets, and detach."""
        # 1. Setup parent bundle asset
        parent_asset = self.env['employee.asset'].create({
            'name': 'Workstation Bundle PC',
            'asset_code': 'AST-BUNDLE-MAIN',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        parent_asset.action_set_to_available()
        self.assertEqual(parent_asset.state, 'available')
        self.assertEqual(parent_asset.child_count, 0)

        # 2. Setup candidate available sub-assets (same company)
        sub_asset_1 = self.env['employee.asset'].create({
            'name': 'Dell UltraSharp 27',
            'asset_code': 'AST-SUB-MON-01',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        sub_asset_1.action_set_to_available()

        sub_asset_2 = self.env['employee.asset'].create({
            'name': 'Mechanical Keyboard',
            'asset_code': 'AST-SUB-KB-01',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        sub_asset_2.action_set_to_available()

        # 3. Setup assigned asset (cannot be bundled)
        assigned_asset = self.env['employee.asset'].create({
            'name': 'Active In-Use Laptop',
            'asset_code': 'AST-IN-USE-01',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        assigned_asset.action_set_to_available()
        assigned_asset.action_assign_asset(employee=self.employee_1)
        self.assertEqual(assigned_asset.state, 'assigned')

        # 4. Setup foreign company asset (cannot be bundled)
        foreign_category = self.env['employee.asset.category'].create({
            'name': 'Foreign Tech',
            'code': 'FT',
            'company_id': self.company_2.id,
        })
        foreign_asset = self.env['employee.asset'].create({
            'name': 'Foreign Monitor',
            'asset_code': 'AST-FOREIGN-01',
            'category_id': foreign_category.id,
            'company_id': self.company_2.id,
        })
        foreign_asset.action_set_to_available()

        # 5. Open wizard action test
        wizard_action = parent_asset.action_open_bundle_wizard()
        self.assertEqual(wizard_action['res_model'], 'asset.bundle.wizard')
        self.assertEqual(wizard_action['context']['default_parent_asset_id'], parent_asset.id)

        # 5b. Verify wizard created with lines, action_select_all, and action_deselect_all
        wizard_inst = self.env['asset.bundle.wizard'].browse(wizard_action['res_id'])
        self.assertTrue(len(wizard_inst.line_ids) >= 2)
        wizard_inst.action_select_all()
        self.assertTrue(all(line.selected for line in wizard_inst.line_ids))
        wizard_inst.action_deselect_all()
        self.assertTrue(not any(line.selected for line in wizard_inst.line_ids))

        # 6. Test wizard validation: cannot attach already assigned asset
        wizard_invalid_assigned = self.env['asset.bundle.wizard'].create({
            'parent_asset_id': parent_asset.id,
            'asset_ids': [(6, 0, [assigned_asset.id])],
        })
        with self.assertRaises(ValidationError):
            wizard_invalid_assigned.action_confirm()

        # 7. Test wizard validation: cannot attach asset from another company
        wizard_invalid_foreign = self.env['asset.bundle.wizard'].create({
            'parent_asset_id': parent_asset.id,
            'asset_ids': [(6, 0, [foreign_asset.id])],
        })
        with self.assertRaises(ValidationError):
            wizard_invalid_foreign.action_confirm()

        # 8. Test wizard validation: cannot bundle asset into itself
        wizard_invalid_self = self.env['asset.bundle.wizard'].create({
            'parent_asset_id': parent_asset.id,
            'asset_ids': [(6, 0, [parent_asset.id])],
        })
        with self.assertRaises(ValidationError):
            wizard_invalid_self.action_confirm()

        # 9. Test attaching multiple available assets via wizard successfully
        wizard_valid = self.env['asset.bundle.wizard'].create({
            'parent_asset_id': parent_asset.id,
            'asset_ids': [(6, 0, [sub_asset_1.id, sub_asset_2.id])],
        })
        wizard_valid.action_confirm()

        # Verify bundling state
        self.assertEqual(sub_asset_1.parent_id.id, parent_asset.id)
        self.assertEqual(sub_asset_2.parent_id.id, parent_asset.id)
        self.assertEqual(parent_asset.child_count, 2)
        self.assertIn(sub_asset_1, parent_asset.child_ids)
        self.assertIn(sub_asset_2, parent_asset.child_ids)

        # 10. Detach one sub-asset from bundle
        sub_asset_1.action_remove_from_bundle()
        self.assertFalse(sub_asset_1.parent_id)
        self.assertEqual(sub_asset_1.state, 'available')
        self.assertEqual(parent_asset.child_count, 1)
        self.assertNotIn(sub_asset_1, parent_asset.child_ids)
        self.assertIn(sub_asset_2, parent_asset.child_ids)

        # 11. Test detach prevention when parent bundle is actively assigned
        parent_asset.action_assign_asset(employee=self.employee_2)
        self.assertEqual(parent_asset.state, 'assigned')
        self.assertEqual(sub_asset_2.state, 'assigned')
        self.assertEqual(sub_asset_2.employee_id.id, self.employee_2.id)

        # Attempting to detach sub_asset_2 must raise UserError
        with self.assertRaises(UserError):
            sub_asset_2.action_remove_from_bundle()

        # Verify it remains attached
        self.assertEqual(sub_asset_2.parent_id.id, parent_asset.id)

    def test_21_dashboard_metrics(self):
        """21. Executive Dashboard: aggregated metrics, real-time KPI counts, categories, and actionable queues."""
        metrics = self.env['employee.asset'].get_dashboard_metrics()
        self.assertIsInstance(metrics, dict)
        self.assertIn('total_assets', metrics)
        self.assertIn('available_assets', metrics)
        self.assertIn('assigned_assets', metrics)
        self.assertIn('utilization_rate', metrics)
        self.assertIn('maintenance_assets', metrics)
        self.assertIn('overdue_count', metrics)
        self.assertIn('warranty_expiring_count', metrics)
        self.assertIn('total_valuation', metrics)
        self.assertIsInstance(metrics['categories'], list)
        self.assertIsInstance(metrics['departments'], list)
        self.assertIsInstance(metrics['urgent_overdue'], list)
        self.assertIsInstance(metrics['recent_allocations'], list)
        self.assertIsInstance(metrics['maintenances'], list)
        self.assertIsInstance(metrics['warranty_expiring'], list)
        self.assertEqual(metrics['company_name'], self.company_1.name)

    def test_22_security_groups_and_employee_record_rules(self):
        """22. Verify 3-tier security architecture and self-service record rules:
        - Regular Employee user only sees their own assigned equipment.
        - Officer user sees all equipment across the company.
        """
        # Create a standard employee user with only Employee self-service group
        emp_user = self.env['res.users'].create({
            'name': 'Standard Employee User',
            'login': 'emp_test_user_01',
            'email': 'emp_test@example.com',
            'company_id': self.company_1.id,
            'company_ids': [(6, 0, [self.company_1.id])],
            'group_ids': [
                (6, 0, [
                    self.env.ref('base.group_user').id,
                    self.env.ref('employee_asset_tracker.group_employee_asset_emp').id,
                ])
            ],
        })

        # Link employee_1 to emp_user
        self.employee_1.write({'user_id': emp_user.id})

        # Asset A: Assigned to employee_1 (emp_user's asset)
        asset_a = self.env['employee.asset'].create({
            'name': 'Employee 1 Laptop',
            'asset_code': 'SEC-AST-01',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        asset_a.action_set_to_available()
        asset_a.action_assign_asset(employee=self.employee_1)

        # Asset B: Assigned to employee_2 (someone else's asset)
        asset_b = self.env['employee.asset'].create({
            'name': 'Employee 2 Laptop',
            'asset_code': 'SEC-AST-02',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        asset_b.action_set_to_available()
        asset_b.action_assign_asset(employee=self.employee_2)

        # Asset C: In-Stock Available Asset (Unassigned)
        asset_c = self.env['employee.asset'].create({
            'name': 'Warehouse Spare Monitor',
            'asset_code': 'SEC-AST-03',
            'category_id': self.category_laptop.id,
            'company_id': self.company_1.id,
        })
        asset_c.action_set_to_available()

        # Query assets as regular employee (Self-Service)
        emp_assets = self.env['employee.asset'].with_user(emp_user).search([
            ('id', 'in', (asset_a.id, asset_b.id, asset_c.id))
        ])

        # Must only see their own assigned asset (asset_a)
        self.assertIn(asset_a, emp_assets)
        self.assertNotIn(asset_b, emp_assets, "Standard employee should not see colleagues' hardware!")
        self.assertNotIn(asset_c, emp_assets, "Standard employee should not see unassigned warehouse stock!")

        # Query assets as Officer
        officer_assets = self.env['employee.asset'].with_user(self.user_asset_officer).search([
            ('id', 'in', (asset_a.id, asset_b.id, asset_c.id))
        ])

        # Officer must see all three assets
        self.assertIn(asset_a, officer_assets)
        self.assertIn(asset_b, officer_assets)
        self.assertIn(asset_c, officer_assets)

