// Copyright (c) 2026, Dux Digitech and contributors
// For license information, please see license.txt

frappe.ui.form.on("AMC Visit", {
	setup(frm) {
		// the contract list shows only contracts that cover the selected asset
		frm.set_query("amc_contract", () => ({
			query: "amc_tracker.amc_tracker.doctype.amc_visit.amc_visit.contracts_for_asset",
			filters: { asset: frm.doc.asset || "" },
		}));
	},
	asset(frm) {
		if (frm.doc.amc_contract) frm.set_value("amc_contract", "");
	},
	status(frm) {
		if (frm.doc.status === "Done" && !frm.doc.done_date) {
			frm.set_value("done_date", frappe.datetime.get_today());
		}
	},
});
