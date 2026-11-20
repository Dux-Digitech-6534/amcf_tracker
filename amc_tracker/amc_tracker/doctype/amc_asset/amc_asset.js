// Copyright (c) 2026, Dux Digitech and contributors
// For license information, please see license.txt

frappe.ui.form.on("AMC Asset", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("AMC Contracts"), () => {
			frappe.set_route("List", "AMC Contract", { assets_summary: ["like", "%(" + frm.doc.name + ")%"] });
		}, __("View"));
		frm.add_custom_button(__("Open in AMC Tracker"), () => frappe.set_route("amc_tracker"));
	},
	purchase_order(frm) {
		fetch_purchase(frm, "Purchase Order", frm.doc.purchase_order, "transaction_date");
	},
	purchase_invoice(frm) {
		fetch_purchase(frm, "Purchase Invoice", frm.doc.purchase_invoice, "posting_date");
	},
});

// fills supplier, date and cost, only where they are still empty
function fetch_purchase(frm, doctype, name, date_field) {
	if (!name) return;
	frappe.db.get_value(doctype, name, ["supplier", date_field, "grand_total"]).then((r) => {
		const d = r.message || {};
		if (!frm.doc.supplier && d.supplier) frm.set_value("supplier", d.supplier);
		if (!frm.doc.purchase_date && d[date_field]) frm.set_value("purchase_date", d[date_field]);
		if (!frm.doc.purchase_cost && d.grand_total) frm.set_value("purchase_cost", d.grand_total);
	});
}
