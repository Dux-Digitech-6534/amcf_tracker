# Copyright (c) 2026, Dux Digitech and contributors
# For license information, please see license.txt

"""Server side of the AMC Tracker page (/app/amc_tracker).

Every method returns {"ok": True, ..., "boot": <fresh data>} or {"ok": False, "msg": "..."}.
The checks that matter (dates, links, permissions, submit rules) live in the DocType controllers,
so the page and the desk forms follow the same rules.
"""

import functools
import json

import frappe
from frappe import _
from frappe.utils import getdate, nowdate, strip_html_tags

from amc_tracker import logic
from amc_tracker.amc_tracker.doctype.amc_contract import amc_contract as contract_mod

ASSET, CONTRACT, VISIT = "AMC Asset", "AMC Contract", "AMC Visit"
KIND = {"asset": ASSET, "contract": CONTRACT, "visit": VISIT}
STATUSES = ("Not started", "Quotation requested", "Quotation received", "WO issued", "Renewed", "Not renewing")


def guarded(fn):
	"""Turn a validation or permission error into {"ok": False, "msg": ...} and undo the half-done work."""

	@functools.wraps(fn)
	def wrapper(*args, **kwargs):
		try:
			return fn(*args, **kwargs)
		except (frappe.ValidationError, frappe.PermissionError) as e:
			frappe.db.rollback()
			frappe.clear_messages()
			return {"ok": False, "msg": strip_html_tags(str(e)) or _("Not allowed.")}

	return wrapper


def _perm(doctype):
	letters = ""
	for letter, ptype in (("r", "read"), ("c", "create"), ("u", "write"), ("d", "delete")):
		if frappe.has_permission(doctype, ptype):
			letters += letter
	if doctype == CONTRACT and frappe.has_permission(doctype, "submit"):
		letters += "s"
	return letters


def _writable(doctype):
	meta = frappe.get_meta(doctype)
	return {df.fieldname for df in meta.fields if df.fieldtype not in frappe.model.no_value_fields and not df.read_only}


def _after_submit_fields():
	return {df.fieldname for df in frappe.get_meta(CONTRACT).fields if df.allow_on_submit}


def _safe(fn, default):
	"""Optional lists (work orders, purchase documents) are left empty when the user may not read them."""
	try:
		return fn()
	except frappe.PermissionError:
		frappe.clear_messages()
		return default


def _masters():
	asset_options = frappe.get_meta(ASSET).get_field("asset_type").options or ""
	return {
		"asset_types": [o for o in asset_options.split("\n") if o],
		"companies": _safe(lambda: frappe.get_list("Company", pluck="name", order_by="name asc", limit_page_length=0), []),
		"suppliers": _safe(
			lambda: frappe.get_list("Supplier", filters={"disabled": 0}, pluck="name", order_by="name asc", limit_page_length=0), []
		),
		"work_orders": _safe(
			lambda: [
				{
					"name": w.name,
					"party": w.supplier,
					"employer": w.company,
					"scope": w.work_title,
					"start": w.scheduled_start_date,
					"end": w.scheduled_completion_date,
					"excl": w.total_amount,
					"tax": w.total_tax_amount,
				}
				for w in frappe.get_list(
					"Work Order Contract",
					filters={"docstatus": 1},
					fields=["name", "supplier", "company", "work_title", "scheduled_start_date", "scheduled_completion_date", "total_amount", "total_tax_amount"],
					order_by="creation desc",
					limit_page_length=500,
				)
			],
			[],
		),
		"purchase_orders": _safe(
			lambda: frappe.get_list("Purchase Order", filters={"docstatus": 1}, pluck="name", order_by="modified desc", limit_page_length=300), []
		),
		"purchase_invoices": _safe(
			lambda: frappe.get_list("Purchase Invoice", filters={"docstatus": 1}, pluck="name", order_by="modified desc", limit_page_length=300), []
		),
		"erp_assets": _safe(lambda: frappe.get_list("Asset", pluck="name", order_by="modified desc", limit_page_length=300), []),
	}


def _boot():
	assets = frappe.get_list(ASSET, fields=["*"], order_by="name asc", limit_page_length=0)
	contracts = frappe.get_list(CONTRACT, fields=["*"], filters={"docstatus": ["<", 2]}, order_by="name asc", limit_page_length=0)
	visits = frappe.get_list(VISIT, fields=["*"], order_by="planned_date asc", limit_page_length=0)

	names = [c.name for c in contracts]
	rows = {}
	if names:
		for r in frappe.get_all(
			"AMC Contract Asset", filters={"parent": ["in", names], "parenttype": CONTRACT}, fields=["parent", "asset"], order_by="idx asc"
		):
			rows.setdefault(r.parent, []).append({"asset": r.asset})

	visible = {ASSET: {a.name for a in assets}, CONTRACT: set(names)}
	files = {}
	for f in frappe.get_all(
		"File",
		filters={"attached_to_doctype": ["in", [ASSET, CONTRACT]], "is_folder": 0},
		fields=["name", "file_name", "file_url", "attached_to_doctype", "attached_to_name", "is_private"],
		order_by="creation asc",
	):
		if f.attached_to_name in visible.get(f.attached_to_doctype, ()):
			files.setdefault((f.attached_to_doctype, f.attached_to_name), []).append(
				{"name": f.name, "file_name": f.file_name, "file_url": f.file_url, "is_private": f.is_private}
			)

	out_assets, out_contracts = [], []
	for a in assets:
		a["id"] = a.name
		a["files"] = files.get((ASSET, a.name), [])
		out_assets.append(a)
	for c in contracts:
		c["id"] = c.name
		c["assets"] = rows.get(c.name, [])
		c["files"] = files.get((CONTRACT, c.name), [])
		out_contracts.append(c)
	for v in visits:
		v["id"] = v.name

	return {
		"ok": True,
		"today": str(getdate(nowdate())),
		"user": {"name": frappe.session.user, "full_name": frappe.db.get_value("User", frappe.session.user, "full_name")},
		"perms": {k: _perm(dt) for k, dt in KIND.items()},
		"after_submit": sorted(_after_submit_fields()),
		"series": logic.ASSET_TYPE_PREFIX,
		"default_prefix": logic.DEFAULT_PREFIX,
		"expiring_days": logic.EXPIRING_DAYS,
		"warranty_days": logic.WARRANTY_DAYS,
		"masters": _masters(),
		"assets": out_assets,
		"contracts": out_contracts,
		"visits": visits,
	}


@frappe.whitelist()
@guarded
def bootstrap():
	return _boot()


def _clean_rows(rows):
	out = []
	for r in rows or []:
		asset = r.get("asset") if isinstance(r, dict) else r
		if asset:
			out.append({"asset": asset})
	return out


def _save(kind, data):
	doctype = KIND[kind]
	data = json.loads(data) if isinstance(data, str) else dict(data or {})
	name = data.get("name") or data.get("id")
	values = {k: (None if v == "" else v) for k, v in data.items() if k in _writable(doctype)}
	rows = _clean_rows(data.get("assets")) if kind == "contract" and "assets" in data else None
	if name:
		doc = frappe.get_doc(doctype, name)
		doc.check_permission("write")
		if kind == "contract" and doc.docstatus == 1:
			# a submitted contract can only change the fields that allow it
			values = {k: v for k, v in values.items() if k in _after_submit_fields()}
			rows = None
		doc.update(values)
		if rows is not None:
			doc.set("assets", [])
			for r in rows:
				doc.append("assets", r)
		doc.save()
	else:
		doc = frappe.new_doc(doctype)
		doc.update(values)
		for r in rows or []:
			doc.append("assets", r)
		doc.insert()
	return doc


@frappe.whitelist()
@guarded
def save_record(kind, data):
	doc = _save(kind, data)
	return {"ok": True, "name": doc.name, "boot": _boot()}


@frappe.whitelist()
@guarded
def delete_record(kind, name):
	frappe.delete_doc(KIND[kind], name)
	return {"ok": True, "boot": _boot()}


@frappe.whitelist()
@guarded
def generate_schedule(name):
	result = contract_mod.build_schedule(name)
	return dict(result, ok=True, boot=_boot())


@frappe.whitelist()
@guarded
def create_renewal(name):
	return {"ok": True, "name": contract_mod.build_renewal(name), "boot": _boot()}


@frappe.whitelist()
@guarded
def submit_contract(name):
	doc = frappe.get_doc(CONTRACT, name)
	doc.check_permission("submit")
	doc.submit()
	return {"ok": True, "name": doc.name, "boot": _boot()}


@frappe.whitelist()
@guarded
def set_renewal_status(name, status):
	if status not in STATUSES:
		frappe.throw(_("Unknown renewal status."))
	doc = frappe.get_doc(CONTRACT, name)
	doc.check_permission("write")
	doc.renewal_status = status
	doc.save()
	return {"ok": True, "boot": _boot()}


@frappe.whitelist()
@guarded
def remove_file(name):
	f = frappe.get_doc("File", name)
	if f.attached_to_doctype not in (ASSET, CONTRACT) or not f.attached_to_name:
		frappe.throw(_("This file does not belong to AMC Tracker."))
	if not frappe.has_permission(f.attached_to_doctype, "write", doc=f.attached_to_name):
		frappe.throw(_("You cannot change this record."))
	frappe.delete_doc("File", name, ignore_permissions=True)
	return {"ok": True, "boot": _boot()}


@frappe.whitelist()
@guarded
def link_info(doctype, name):
	"""Values the form copies from a Work Order Contract, Purchase Order or Purchase Invoice."""
	fields = {
		"Work Order Contract": ["supplier", "company", "work_title", "scheduled_start_date", "scheduled_completion_date", "total_amount", "total_tax_amount"],
		"Purchase Order": ["supplier", "transaction_date", "grand_total"],
		"Purchase Invoice": ["supplier", "posting_date", "grand_total"],
	}
	if doctype not in fields:
		frappe.throw(_("Not allowed."))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(_("You cannot read {0}.").format(name))
	info = frappe.db.get_value(doctype, name, fields[doctype], as_dict=True)
	if not info:
		frappe.throw(_("{0} was not found.").format(name))
	return {"ok": True, "info": info}
