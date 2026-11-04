/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class EmployeeAssetDashboard extends Component {
    static template = "employee_asset_tracker.EmployeeAssetDashboard";
    static props = {
        ...standardActionServiceProps,
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            isRefreshing: false,
            metrics: {
                company_name: "",
                currency_symbol: "$",
                total_assets: 0,
                available_assets: 0,
                assigned_assets: 0,
                utilization_rate: 0,
                maintenance_assets: 0,
                retired_assets: 0,
                lost_assets: 0,
                overdue_count: 0,
                warranty_expiring_count: 0,
                total_valuation: "$0.00",
                categories: [],
                departments: [],
                urgent_overdue: [],
                recent_allocations: [],
                maintenances: [],
                warranty_expiring: [],
            },
        });

        onWillStart(async () => {
            await this.loadMetrics();
        });
    }

    async loadMetrics() {
        try {
            const data = await this.orm.call("employee.asset", "get_dashboard_metrics", []);
            if (data) {
                this.state.metrics = data;
            }
        } catch (error) {
            this.notification.add(
                _t("Failed to load asset dashboard metrics: ") + (error?.data?.message || error?.message || ""),
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    async onRefresh() {
        this.state.isRefreshing = true;
        await this.loadMetrics();
        setTimeout(() => {
            this.state.isRefreshing = false;
        }, 400);
        this.notification.add(_t("Dashboard updated with real-time asset intelligence."), {
            type: "info",
        });
    }

    // Quick Actions
    openScanWizard() {
        this.actionService.doAction("employee_asset_tracker.action_asset_scan_wizard");
    }

    openCreateAsset() {
        this.actionService.doAction({
            name: _t("Register New Asset"),
            type: "ir.actions.act_window",
            res_model: "employee.asset",
            views: [[false, "form"]],
            target: "current",
        });
    }

    openAssignWizard() {
        this.actionService.doAction({
            name: _t("Assign Asset to Employee"),
            type: "ir.actions.act_window",
            res_model: "asset.assign.wizard",
            views: [[false, "form"]],
            target: "new",
        });
    }

    // Metric Navigation Clicks
    openAllAssets() {
        this.actionService.doAction({
            name: _t("All Hardware Assets"),
            type: "ir.actions.act_window",
            res_model: "employee.asset",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: [],
            context: { search_default_group_by_category: 1 },
        });
    }

    openAvailableAssets() {
        this.actionService.doAction({
            name: _t("Available in Stock"),
            type: "ir.actions.act_window",
            res_model: "employee.asset",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: [["state", "=", "available"]],
        });
    }

    openAssignedAssets() {
        this.actionService.doAction({
            name: _t("Assigned / Deployed Assets"),
            type: "ir.actions.act_window",
            res_model: "employee.asset",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: [["state", "=", "assigned"]],
        });
    }

    openMaintenanceAssets() {
        this.actionService.doAction({
            name: _t("Assets Under Maintenance"),
            type: "ir.actions.act_window",
            res_model: "employee.asset",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: [["state", "=", "maintenance"]],
        });
    }

    openOverdueAssignments() {
        this.actionService.doAction({
            name: _t("Overdue Asset Allocations"),
            type: "ir.actions.act_window",
            res_model: "employee.asset.assignment",
            views: [[false, "list"], [false, "form"]],
            domain: [["is_overdue", "=", true]],
        });
    }

    openExpiringWarranties() {
        this.actionService.doAction({
            name: _t("Warranties Expiring Soon (30 Days)"),
            type: "ir.actions.act_window",
            res_model: "employee.asset",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: [["warranty_status", "=", "expiring"]],
        });
    }

    openAllMaintenances() {
        this.actionService.doAction({
            name: _t("Maintenance Operations"),
            type: "ir.actions.act_window",
            res_model: "employee.asset.maintenance",
            views: [[false, "list"], [false, "form"]],
            domain: [],
        });
    }

    openAllAssignments() {
        this.actionService.doAction({
            name: _t("Assignment History"),
            type: "ir.actions.act_window",
            res_model: "employee.asset.assignment",
            views: [[false, "list"], [false, "form"]],
            domain: [],
        });
    }

    openCategoryAssets(categoryId, categoryName) {
        this.actionService.doAction({
            name: categoryName + _t(" Assets"),
            type: "ir.actions.act_window",
            res_model: "employee.asset",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: [["category_id", "=", categoryId]],
        });
    }

    openAsset(assetId) {
        if (!assetId) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "employee.asset",
            res_id: assetId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openAssignment(assignmentId) {
        if (!assignmentId) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "employee.asset.assignment",
            res_id: assignmentId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openMaintenance(maintId) {
        if (!maintId) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "employee.asset.maintenance",
            res_id: maintId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("employee_asset_dashboard", EmployeeAssetDashboard);
