# Copyright (c) 2026, Dux Digitech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate

from amc_tracker import logic
from amc_tracker.amc_tracker.doctype.amc_asset.amc_asset import refresh_assets

# Fields copied into a renewal draft
RENEWAL_COPY = (
	"vendor", "vendor_contact", "vendor_phone", "vendor_email", "contract_type", "gst_percent", "payment_terms",
	"yearly_escalation_percent", "remind_before_days", "visit_frequency", "visits_per_year", "extra_visit_charge",
	"breakdown_response", "scope", "exclusions",
)


class AMCContract(Document):
	def validate(self):
		self.fill_from_work_order()
		self.validate_period()
		self.validate_assets()
		self.validate_numbers()
		self.compute()

	def fill_from_work_order(self):
		"""Work Order Contract fills the contractor, dates and amount where those are still empty."""
		if not self.work_order:
			return
		wo = frappe.db.get_value(
			"Work Order Contract",
			self.work_order,
			["supplier", "scheduled_start_date", "scheduled_completion_date", "total_amount"],
			as_dict=True,
		)
		if not wo:
			return
		if not self.vendor:
			self.vendor = wo.get("supplier")
		if not self.start_date:
			self.start_date = wo.get("scheduled_start_date")
		if not self.end_date:
			self.end_date = wo.get("scheduled_completion_date")
		if not flt(self.value_excl_gst):
			self.value_excl_gst = wo.get("total_amount")

	def validate_period(self):
		if self.start_date and self.end_date and getdate(self.end_date) <= getdate(self.start_date):
			frappe.throw(_("End date must be after the start date."))

	def validate_assets(self):
		assets = [row.asset for row in self.get("assets") if row.asset]
		if not assets:
			frappe.throw(_("Add at least one asset under Assets covered."))
		if len(assets) != len(set(assets)):
			frappe.throw(_("The same asset is added twice under Assets covered."))

	def validate_numbers(self):
		if flt(self.value_excl_gst) < 0:
			frappe.throw(_("Value cannot be negative."))
		if not 0 <= flt(self.gst_percent) <= 100:
			frappe.throw(_("GST % must be between 0 and 100."))
		if self.remind_before_days is not None and self.remind_before_days < 0:
			frappe.throw(_("Remind before (days) cannot be negative."))
		if self.previous_contract and self.previous_contract == self.name:
			frappe.throw(_("A contract cannot be its own previous contract."))

	def compute(self):
		self.total_incl_gst = logic.total_incl_gst(flt(self.value_excl_gst), flt(self.gst_percent))
		self.set_status()
		self.assets_summary = ", ".join(
			"{0} ({1})".format(row.asset_name, row.asset) if row.asset_name else row.asset for row in self.get("assets") if row.asset
		)

	def set_status(self):
		if self.start_date and self.end_date:
			status, days = logic.contract_status(getdate(self.start_date), getdate(self.end_date), getdate(nowdate()))
			self.contract_status = status or None
			self.days_left = days

	def before_update_after_submit(self):
		self.set_status()

	def on_submit(self):
		if self.previous_contract:
			frappe.db.set_value(
				"AMC Contract",
				self.previous_contract,
				{"renewal_status": "Renewed", "next_contract": self.name},
				update_modified=False,
			)
		self.refresh_covered_assets()

	def on_cancel(self):
		if self.previous_contract and frappe.db.get_value("AMC Contract", self.previous_contract, "next_contract") == self.name:
			frappe.db.set_value(
				"AMC Contract",
				self.previous_contract,
				{"renewal_status": "Not started", "next_contract": None},
				update_modified=False,
			)
		self.refresh_covered_assets()

	def refresh_covered_assets(self):
		refresh_assets([row.asset for row in self.get("assets")])


def build_schedule(name):
	"""Create a Planned AMC Visit for every covered asset at each interval. Same contract + asset + date is never created twice."""
	contract = frappe.get_doc("AMC Contract", name)
	contract.check_permission("read")
	frappe.has_permission("AMC Visit", "create", throw=True)
	try:
		dates = logic.schedule_dates(
			getdate(contract.start_date), getdate(contract.end_date), contract.visit_frequency, getdate(nowdate())
		)
	except ValueError as e:
		frappe.throw(str(e))
	existing = {
		(row.asset, getdate(row.planned_date))
		for row in frappe.get_all("AMC Visit", filters={"amc_contract": name}, fields=["asset", "planned_date"])
	}
	created = skipped = 0
	for asset in [row.asset for row in contract.assets]:
		for d in dates:
			if (asset, d) in existing:
				skipped += 1
				continue
			frappe.get_doc(
				{
					"doctype": "AMC Visit",
					"asset": asset,
					"amc_contract": name,
					"visit_type": "Preventive",
					"status": "Planned",
					"planned_date": d,
				}
			).insert()
			existing.add((asset, d))
			created += 1
	return {"created": created, "skipped": skipped}


def build_renewal(name):
	"""A new draft contract one year ahead, value raised by the yearly escalation, same assets."""
	old = frappe.get_doc("AMC Contract", name)
	old.check_permission("read")
	frappe.has_permission("AMC Contract", "create", throw=True)
	other = frappe.db.get_value("AMC Contract", {"previous_contract": name, "docstatus": ["<", 2]}, "name")
	if other:
		frappe.throw(_("A renewal of this contract already exists: {0}").format(other))
	start, end, value = logic.renewal_values(
		getdate(old.start_date), getdate(old.end_date), flt(old.value_excl_gst), flt(old.yearly_escalation_percent)
	)
	new = frappe.new_doc("AMC Contract")
	for field in RENEWAL_COPY:
		new.set(field, old.get(field))
	new.update(
		{"start_date": start, "end_date": end, "value_excl_gst": value, "renewal_status": "Not started", "previous_contract": old.name}
	)
	for row in old.assets:
		new.append("assets", {"asset": row.asset})
	new.insert()
	return new.name


@frappe.whitelist()
def generate_visit_schedule(name):
	"""Desk button: Generate Visit Schedule."""
	result = build_schedule(name)
	frappe.msgprint(
		_("{0} planned visit(s) created. {1} already existed and were skipped.").format(result["created"], result["skipped"])
	)
	return result


@frappe.whitelist()
def create_renewal(name):
	"""Desk button: Create Renewal."""
	return build_renewal(name)
