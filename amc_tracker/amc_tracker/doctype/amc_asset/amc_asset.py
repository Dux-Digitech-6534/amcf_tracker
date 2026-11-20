# Copyright (c) 2026, Dux Digitech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, getdate, nowdate

from amc_tracker import logic


class AMCAsset(Document):
	def autoname(self):
		self.name = make_autoname(logic.prefix_for(self.asset_type) + "-.###")

	def validate(self):
		self.validate_values()
		self.fetch_purchase_details()
		self.update_computed()

	def validate_values(self):
		# "Other" needs a text saying what it is; any other type clears it
		if self.meta.has_field("asset_type_other"):
			if self.asset_type == "Other":
				self.asset_type_other = (self.get("asset_type_other") or "").strip()
				if not self.asset_type_other:
					frappe.throw(_("Please say what the other asset type is."))
			else:
				self.asset_type_other = None
		if self.warranty_start and self.warranty_end and getdate(self.warranty_end) < getdate(self.warranty_start):
			frappe.throw(_("Warranty end cannot be before warranty start."))
		if flt(self.purchase_cost) < 0:
			frappe.throw(_("Purchase cost cannot be negative."))
		if flt(self.expected_life_years) < 0:
			frappe.throw(_("Expected life cannot be negative."))

	def fetch_purchase_details(self):
		"""A Purchase Order or Purchase Invoice fills supplier, date and total where those are still empty."""
		for doctype, field, date_field in (
			("Purchase Order", "purchase_order", "transaction_date"),
			("Purchase Invoice", "purchase_invoice", "posting_date"),
		):
			name = self.get(field)
			if not name:
				continue
			row = frappe.db.get_value(doctype, name, ["supplier", date_field, "grand_total"], as_dict=True)
			if not row:
				continue
			if not self.supplier:
				self.supplier = row.get("supplier")
			if not self.purchase_date:
				self.purchase_date = row.get(date_field)
			if not self.purchase_cost:
				self.purchase_cost = row.get("grand_total")

	def update_computed(self, today=None):
		values = compute_for_asset(self.name, self.warranty_end, self.purchase_cost, today)
		self.update(values)
		return values


def compute_for_asset(name, warranty_end, purchase_cost, today=None):
	"""Warranty, AMC, visit dates and cost of ownership for one asset."""
	today = getdate(today or nowdate())
	contracts = frappe.db.sql(
		"""
		select c.name, c.start_date, c.end_date, c.total_incl_gst,
			(select count(*) from `tabAMC Contract Asset` x
				where x.parent = c.name and x.parenttype = 'AMC Contract') as asset_count
		from `tabAMC Contract` c
		where c.docstatus = 1
			and c.name in (select parent from `tabAMC Contract Asset`
				where asset = %s and parenttype = 'AMC Contract')
		""",
		(name,),
		as_dict=True,
	)
	state = logic.asset_amc_state(
		[{"name": c.name, "start": getdate(c.start_date), "end": getdate(c.end_date)} for c in contracts], today
	)
	last_visit = frappe.db.sql(
		"select max(coalesce(done_date, planned_date)) from `tabAMC Visit` where asset = %s and status = 'Done'",
		(name,),
	)[0][0]
	next_visit = frappe.db.sql(
		"select min(planned_date) from `tabAMC Visit` where asset = %s and status = 'Planned'", (name,)
	)[0][0]
	charges = frappe.db.sql(
		"select coalesce(sum(extra_charge), 0) from `tabAMC Visit` where asset = %s and status != 'Cancelled'",
		(name,),
	)[0][0]
	cost = logic.cost_of_ownership(flt(purchase_cost), [(flt(c.total_incl_gst), c.asset_count) for c in contracts], flt(charges))
	return {
		"warranty_status": logic.warranty_status(getdate(warranty_end) if warranty_end else None, today),
		"current_amc": state[0] or None,
		"amc_status": state[1],
		# Int columns cannot be NULL: an asset with no AMC stores 0 (its AMC status says "No AMC")
		"amc_days_left": state[2] if state[2] is not None else 0,
		"last_visit_date": last_visit,
		"next_visit_date": next_visit,
		"total_cost_of_ownership": cost["total"],
	}


def refresh_assets(names, today=None):
	"""Recompute the stored computed fields of the given assets (used after a visit or contract changes and by the daily job)."""
	for name in {n for n in names if n}:
		row = frappe.db.get_value("AMC Asset", name, ["warranty_end", "purchase_cost"], as_dict=True)
		if not row:
			continue
		values = compute_for_asset(name, row.warranty_end, row.purchase_cost, today)
		frappe.db.set_value("AMC Asset", name, values, update_modified=False)
