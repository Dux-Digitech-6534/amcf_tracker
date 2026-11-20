# Copyright (c) 2026, Dux Digitech and contributors
# For license information, please see license.txt

"""Optional starting records (4 assets, 3 contracts). Not run on install.

Only records whose Company and Supplier already exist are created; the rest are reported and skipped, so nothing is
invented in the master data. Look first (nothing is saved):

	bench --site <site> execute amc_tracker.seed.run

Then save (add campus_pune / campus_nagpur if your Company names differ):

	bench --site <site> execute amc_tracker.seed.run --kwargs '{"dry_run": 0}'
"""

import frappe

PUNE = "GHREMF Society Pune"
NAGPUR = "GH Raisoni College Of Engineering And Management Nagpur"

ASSETS = [
	{"key": "LFT-001", "asset_name": "Lift – D Building", "asset_type": "Lift / Elevator", "capacity": "884 kg", "make": "KONE", "site_building": "GHRCACS – D Building", "campus": "pune"},
	{"key": "RO-001", "asset_name": "RO Plant 500 LPH", "asset_type": "RO / Water Treatment", "capacity": "500 LPH", "campus": "pune"},
	{"key": "RO-002", "asset_name": "RO Plant 1000 LPH", "asset_type": "RO / Water Treatment", "capacity": "1000 LPH", "campus": "pune"},
	{"key": "DG-001", "asset_name": "DG Set 200 KVA", "asset_type": "DG Set", "capacity": "200 KVA", "make": "Caterpillar", "model": "3306 DITA", "serial_no": "1RD03636", "campus": "nagpur"},
]

CONTRACTS = [
	{"vendor": "KONE Elevator India Pvt Ltd", "work_order": "WO-GHREMFP-2026-0001-1", "assets": ["LFT-001"], "start_date": "2026-01-01", "end_date": "2026-12-31", "value_excl_gst": 40077, "gst_percent": 18, "payment_terms": "100% advance", "visit_frequency": "Monthly", "visits_per_year": 12},
	{"vendor": "Enviro India", "work_order": "WO-GHREMFP-2026-0002-1", "assets": ["RO-001", "RO-002"], "start_date": "2026-04-01", "end_date": "2027-03-31", "value_excl_gst": 80000, "gst_percent": 18, "payment_terms": "Half yearly", "visit_frequency": "Monthly", "visits_per_year": 12},
	{"vendor": "GMMCO Limited", "work_order": "WO-GHRCEMN-2026-0001", "assets": ["DG-001"], "start_date": "2026-05-03", "end_date": "2027-05-02", "value_excl_gst": 31250, "gst_percent": 18, "payment_terms": "100% advance", "visit_frequency": "Quarterly", "visits_per_year": 4, "extra_visit_charge": 7000, "yearly_escalation_percent": 10},
]


def run(dry_run=1, campus_pune=PUNE, campus_nagpur=NAGPUR):
	dry_run = int(dry_run)
	campuses = {"pune": campus_pune, "nagpur": campus_nagpur}
	report = {"dry_run": dry_run, "created": [], "skipped": []}
	made = {}  # seed key -> real AMC Asset name

	for a in ASSETS:
		campus = campuses[a["campus"]]
		if not frappe.db.exists("Company", campus):
			report["skipped"].append("{0}: Company '{1}' does not exist".format(a["key"], campus))
			continue
		existing = frappe.db.get_value("AMC Asset", {"asset_name": a["asset_name"], "campus": campus}, "name")
		if existing:
			made[a["key"]] = existing
			report["skipped"].append("{0}: already there as {1}".format(a["key"], existing))
			continue
		if dry_run:
			made[a["key"]] = "(new) " + a["key"]
			report["created"].append("{0} {1}".format(a["key"], a["asset_name"]))
			continue
		values = {k: v for k, v in a.items() if k not in ("key", "campus")}
		doc = frappe.get_doc(dict(values, doctype="AMC Asset", campus=campus)).insert()
		made[a["key"]] = doc.name
		report["created"].append("{0} {1}".format(doc.name, doc.asset_name))

	for c in CONTRACTS:
		label = "{0} ({1})".format(c["vendor"], c["work_order"])
		if not frappe.db.exists("Supplier", c["vendor"]):
			report["skipped"].append("{0}: Supplier does not exist".format(label))
			continue
		if not all(k in made for k in c["assets"]):
			report["skipped"].append("{0}: its asset was not created".format(label))
			continue
		if frappe.db.exists("AMC Contract", {"vendor": c["vendor"], "start_date": c["start_date"], "end_date": c["end_date"], "docstatus": ["<", 2]}):
			report["skipped"].append("{0}: already there".format(label))
			continue
		if dry_run:
			report["created"].append(label)
			continue
		values = {k: v for k, v in c.items() if k not in ("assets", "work_order")}
		if frappe.db.exists("Work Order Contract", c["work_order"]):
			values["work_order"] = c["work_order"]
		doc = frappe.get_doc(dict(values, doctype="AMC Contract", assets=[{"asset": made[k]} for k in c["assets"]])).insert()
		doc.submit()
		report["created"].append("{0} {1}".format(doc.name, label))

	if not dry_run:
		frappe.db.commit()
	return report
