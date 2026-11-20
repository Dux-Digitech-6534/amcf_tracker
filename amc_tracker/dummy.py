# Copyright (c) 2026, Dux Digitech and contributors
# For license information, please see license.txt

"""Dummy records for trying AMC Tracker out. Everything made here can be removed again.

The records are tagged: every asset name ends with " (dummy)" and every contract note starts with "DUMMY DATA".
Only the four AMC tables are written. Companies and Suppliers are only linked to, never created or changed.

Look first (nothing is saved), then add, then remove when you are done:

	bench --site <site> execute amc_tracker.dummy.run
	bench --site <site> execute amc_tracker.dummy.run --kwargs '{"dry_run": 0}'
	bench --site <site> execute amc_tracker.dummy.remove --kwargs '{"dry_run": 0}'
"""

from datetime import date

import frappe
from frappe.utils import add_days, getdate, nowdate

from amc_tracker import logic

TAG = " (dummy)"
NOTE = "DUMMY DATA"


def _assets(today, campuses, vendor_lift):
	return [
		{"key": "lift", "asset_name": "Lift – D Building", "asset_type": "Lift / Elevator", "capacity": "884 kg", "make": "KONE", "site_building": "GHRCACS – D Building", "campus": campuses["pune"]},
		{"key": "ro500", "asset_name": "RO Plant 500 LPH", "asset_type": "RO / Water Treatment", "capacity": "500 LPH", "campus": campuses["pune"]},
		{"key": "ro1000", "asset_name": "RO Plant 1000 LPH", "asset_type": "RO / Water Treatment", "capacity": "1000 LPH", "campus": campuses["pune"]},
		{"key": "dg", "asset_name": "DG Set 200 KVA", "asset_type": "DG Set", "capacity": "200 KVA", "make": "Caterpillar", "model": "3306 DITA", "serial_no": "1RD03636", "campus": campuses["nagpur"]},
		{
			"key": "cctv", "asset_name": "NVR 32-channel", "asset_type": "CCTV / Security", "capacity": "32 ch", "make": "Hikvision",
			"site_building": "Admin block", "campus": campuses["pune"], "supplier": vendor_lift, "purchase_cost": 186500,
			"purchase_date": add_days(today, -318), "installation_date": add_days(today, -310), "expected_life_years": 7,
			"warranty_start": add_days(today, -325), "warranty_end": add_days(today, 40),
			"warranty_provider": "Hikvision India Pvt Ltd", "warranty_terms": "Parts and labour, 1 year",
		},
		{
			"key": "ups", "asset_name": "UPS 20 kVA", "asset_type": "UPS / Inverter", "capacity": "20 kVA", "make": "Delta",
			"site_building": "Server room", "campus": campuses["nagpur"],
			"warranty_start": date(2022, 1, 10), "warranty_end": date(2025, 1, 9), "warranty_provider": "Delta Power Solutions",
		},
	]


def _contracts(vendors):
	return [
		{"key": "A", "vendor": vendors["lift"], "assets": ["lift"], "start_date": date(2026, 1, 1), "end_date": date(2026, 12, 31), "value_excl_gst": 40077, "gst_percent": 18, "payment_terms": "100% advance", "visit_frequency": "Monthly", "visits_per_year": 12},
		{"key": "B", "vendor": vendors["ro"], "assets": ["ro500", "ro1000"], "start_date": date(2026, 4, 1), "end_date": date(2027, 3, 31), "value_excl_gst": 80000, "gst_percent": 18, "payment_terms": "Half yearly", "visit_frequency": "Monthly", "visits_per_year": 12},
		{"key": "C", "vendor": vendors["dg"], "assets": ["dg"], "start_date": date(2026, 5, 3), "end_date": date(2027, 5, 2), "value_excl_gst": 31250, "gst_percent": 18, "payment_terms": "100% advance", "visit_frequency": "Quarterly", "visits_per_year": 4, "extra_visit_charge": 7000, "yearly_escalation_percent": 10},
		{"key": "D", "vendor": vendors["ups"], "assets": ["ups"], "start_date": date(2025, 4, 1), "end_date": date(2026, 3, 31), "value_excl_gst": 24000, "gst_percent": 18, "payment_terms": "Half yearly", "visit_frequency": "Quarterly", "visits_per_year": 4},
	]


ENGINEER = {"A": "R. Deshmukh", "B": "S. Patil", "C": "A. Khan", "D": "M. Rao"}
WORK = {
	"A": "Routine service, safety circuit and door check",
	"B": "Backwash, filter check, membrane pressure noted",
	"C": "Oil and filter check, battery test, no-load run",
	"D": "Battery and load check",
}


def _visits(contracts, today):
	"""Planned visits from each contract's schedule. Past ones are mostly Done; the latest past visit of some stays overdue."""
	out = []
	for c in contracts:
		dates = logic.schedule_dates(c["start_date"], c["end_date"], c["visit_frequency"], today, include_past=True)
		past = [d for d in dates if d < today]
		last_past = past[-1] if past else None
		for key in c["assets"]:
			for d in dates:
				v = {"asset": key, "contract": c["key"], "planned_date": d, "visit_type": "Preventive", "status": "Planned"}
				if d < today:
					overdue = d == last_past and (c["key"] in ("A", "C") or (c["key"] == "B" and key == "ro1000"))
					missed = (c["key"] == "A" and d == date(2026, 9, 1)) or (c["key"] == "D" and date(2025, 10, 1) <= d < date(2026, 1, 1))
					if overdue:
						pass
					elif missed:
						v["status"] = "Missed"
					else:
						v.update(status="Done", done_date=d, engineer=ENGINEER[c["key"]], hours_on_site=3 if c["key"] == "C" else 1.5, work_done=WORK[c["key"]])
				out.append(v)
	out.append({"asset": "dg", "contract": "C", "visit_type": "Breakdown", "status": "Done", "planned_date": add_days(today, -57), "done_date": add_days(today, -57), "engineer": "A. Khan", "hours_on_site": 5, "work_done": "Fuel injector replaced, test run 30 min", "parts_replaced": "Injector nozzle x1", "extra_charge": 7000, "next_action": "Re-check after 100 hrs"})
	out.append({"asset": "ro500", "contract": None, "visit_type": "Membrane cleaning", "status": "Done", "planned_date": add_days(today, -91), "done_date": add_days(today, -91), "engineer": "S. Patil", "hours_on_site": 4, "work_done": "Chemical cleaning of membrane (paid, outside AMC)", "extra_charge": 4500})
	out.append({"asset": "dg", "contract": "C", "visit_type": "Inspection", "status": "Planned", "planned_date": add_days(today, 2)})
	return out


def run(
	dry_run=1,
	campus_pune="Sunrise Institute of Technology",
	campus_nagpur="GH Raisoni Skill Tech University Nagpur",
	vendor_lift="Marina Electricals-VM0015",
	vendor_ro="AquaPure Water Services",
	vendor_dg="Shakti Fuel Centre",
	vendor_ups=None,
):
	"""Add the dummy assets, contracts and visits. With dry_run=1 (the default) only the plan is returned."""
	dry_run = int(dry_run)
	today = getdate(nowdate())
	campuses = {"pune": campus_pune, "nagpur": campus_nagpur}
	vendors = {"lift": vendor_lift, "ro": vendor_ro, "dg": vendor_dg, "ups": vendor_ups or vendor_lift}

	problems = [
		"{0} '{1}' does not exist".format(doctype, name)
		for doctype, name in [("Company", c) for c in campuses.values()] + [("Supplier", v) for v in set(vendors.values())]
		if not frappe.db.exists(doctype, name)
	]
	if frappe.db.exists("AMC Asset", {"asset_name": ["like", "%" + TAG.strip()]}):
		problems.append("dummy data is already there; run amc_tracker.dummy.remove first")
	if problems:
		return {"ok": False, "problems": problems}

	assets = _assets(today, campuses, vendor_lift)
	contracts = _contracts(vendors)
	visits = _visits(contracts, today)
	by_status = {}
	for v in visits:
		by_status[v["status"]] = by_status.get(v["status"], 0) + 1
	plan = {
		"campuses": campuses,
		"vendors": vendors,
		"assets": len(assets),
		"contracts": len(contracts),
		"visits": len(visits),
		"visits_by_status": by_status,
	}
	if dry_run:
		return {"ok": True, "dry_run": 1, "plan": plan}

	try:
		made = {}
		for a in assets:
			values = {k: v for k, v in a.items() if k != "key"}
			values["asset_name"] = a["asset_name"] + TAG
			made[a["key"]] = frappe.get_doc(dict(values, doctype="AMC Asset")).insert().name
		cmade = {}
		for c in contracts:
			values = {k: v for k, v in c.items() if k not in ("key", "assets")}
			doc = frappe.get_doc(
				dict(values, doctype="AMC Contract", notes=NOTE, remind_before_days=60, assets=[{"asset": made[k]} for k in c["assets"]])
			).insert()
			doc.submit()
			cmade[c["key"]] = doc.name
		for v in visits:
			values = {k: val for k, val in v.items() if k not in ("asset", "contract")}
			frappe.get_doc(
				dict(values, doctype="AMC Visit", asset=made[v["asset"]], amc_contract=cmade[v["contract"]] if v["contract"] else None)
			).insert()
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		raise
	return {"ok": True, "dry_run": 0, "created": {"assets": sorted(made.values()), "contracts": sorted(cmade.values()), "visits": len(visits)}, "plan": plan}


def remove(dry_run=1):
	"""Remove only what run() made: assets ending in ' (dummy)', their visits, and contracts whose note starts with DUMMY DATA."""
	dry_run = int(dry_run)
	assets = frappe.get_all("AMC Asset", filters={"asset_name": ["like", "%" + TAG.strip()]}, pluck="name")
	if not assets:
		return {"ok": True, "removed": 0, "note": "no dummy data found"}
	visits = frappe.get_all("AMC Visit", filters={"asset": ["in", assets]}, pluck="name")
	contracts = frappe.get_all("AMC Contract", filters={"notes": ["like", NOTE + "%"]}, fields=["name", "docstatus"])
	report = {"ok": True, "dry_run": dry_run, "assets": len(assets), "contracts": len(contracts), "visits": len(visits)}
	if dry_run:
		return report
	try:
		for name in visits:
			frappe.delete_doc("AMC Visit", name, ignore_permissions=True)
		for c in contracts:
			doc = frappe.get_doc("AMC Contract", c.name)
			if doc.docstatus == 1:
				doc.cancel()
		for name in assets:
			frappe.db.set_value("AMC Asset", name, "current_amc", None, update_modified=False)
		for c in contracts:
			frappe.delete_doc("AMC Contract", c.name, ignore_permissions=True)
		for name in assets:
			frappe.delete_doc("AMC Asset", name, ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		raise
	return report
