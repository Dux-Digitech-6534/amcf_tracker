// Copyright (c) 2026, Dux Digitech and contributors
// For license information, please see license.txt

const AMC_CONTRACT = "amc_tracker.amc_tracker.doctype.amc_contract.amc_contract.";

frappe.ui.form.on("AMC Contract", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.docstatus < 2) {
			frm.add_custom_button(__("Generate Visit Schedule"), () => {
				frappe.call({
					method: AMC_CONTRACT + "generate_visit_schedule",
					args: { name: frm.doc.name },
					freeze: true,
				});
			}, __("Actions"));
			frm.add_custom_button(__("Create Renewal"), () => {
				frappe.call({
					method: AMC_CONTRACT + "create_renewal",
					args: { name: frm.doc.name },
					freeze: true,
					callback: (r) => r.message && frappe.set_route("Form", "AMC Contract", r.message),
				});
			}, __("Actions"));
		}
	},
	work_order(frm) {
		if (!frm.doc.work_order) return;
		frappe.db
			.get_value("Work Order Contract", frm.doc.work_order, [
				"supplier",
				"scheduled_start_date",
				"scheduled_completion_date",
				"total_amount",
				"total_tax_amount",
			])
			.then((r) => {
				const wo = r.message || {};
				frm.set_value("vendor", wo.supplier);
				frm.set_value("start_date", wo.scheduled_start_date);
				frm.set_value("end_date", wo.scheduled_completion_date);
				frm.set_value("value_excl_gst", wo.total_amount);
				if (wo.total_amount && wo.total_tax_amount) {
					frm.set_value("gst_percent", Math.round((wo.total_tax_amount / wo.total_amount) * 10000) / 100);
				}
			});
	},
});
