# Copyright (c) 2026, Dux Digitech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate

from amc_tracker import logic
from amc_tracker.amc_tracker.doctype.amc_asset.amc_asset import refresh_assets


class AMCVisit(Document):
	def validate(self):
		# "Other" needs a text saying what it is; any other type clears it
		if self.meta.has_field("visit_type_other"):
			if self.visit_type == "Other":
				self.visit_type_other = (self.get("visit_type_other") or "").strip()
				if not self.visit_type_other:
					frappe.throw(_("Please say what the other visit type is."))
			else:
				self.visit_type_other = None
		self.check_contract_covers_asset()
		if flt(self.extra_charge) < 0:
			frappe.throw(_("Extra charge cannot be negative."))
		if flt(self.hours_on_site) < 0:
			frappe.throw(_("Hours on site cannot be negative."))
		if self.status == "Done" and not self.done_date:
			self.done_date = nowdate()
		planned = getdate(self.planned_date) if self.planned_date else None
		self.is_overdue = 1 if logic.is_overdue(self.status, planned, getdate(nowdate())) else 0

	def check_contract_covers_asset(self):
		if not self.amc_contract:
			return
		covered = frappe.db.exists(
			"AMC Contract Asset", {"parent": self.amc_contract, "parenttype": "AMC Contract", "asset": self.asset}
		)
		if not covered:
			frappe.throw(_("AMC Contract {0} does not cover asset {1}.").format(self.amc_contract, self.asset))

	def on_update(self):
		names = [self.asset]
		before = self.get_doc_before_save()
		if before and before.asset != self.asset:
			names.append(before.asset)
		refresh_assets(names)

	def after_delete(self):
		refresh_assets([self.asset])


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def contracts_for_asset(doctype, txt, searchfield, start, page_len, filters):
	"""Link search for AMC Visit > AMC Contract: only contracts that cover the selected asset."""
	asset = (filters or {}).get("asset") or ""
	return frappe.db.sql(
		"""
		select c.name, c.vendor, concat(c.start_date, ' to ', c.end_date)
		from `tabAMC Contract` c
		where c.docstatus < 2
			and (%(asset)s = '' or c.name in (select parent from `tabAMC Contract Asset`
				where asset = %(asset)s and parenttype = 'AMC Contract'))
			and (c.name like %(txt)s or c.vendor like %(txt)s)
		order by c.end_date desc
		limit %(start)s, %(page_len)s
		""",
		{"asset": asset, "txt": "%{0}%".format(txt), "start": int(start), "page_len": int(page_len)},
	)
