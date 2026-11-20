# Copyright (c) 2026, Dux Digitech and contributors
# For license information, please see license.txt

"""Daily job: recompute statuses, then tell every AMC Manager what needs attention."""

import frappe
from frappe.utils import escape_html, formatdate, getdate, nowdate

from amc_tracker import logic
from amc_tracker.amc_tracker.doctype.amc_asset import amc_asset


def daily():
	today = getdate(nowdate())
	refresh_all(today)
	frappe.db.commit()
	notify_managers(today)


def refresh_all(today):
	"""Recompute status and days left on every asset, contract and visit."""
	amc_asset.refresh_assets(frappe.get_all("AMC Asset", pluck="name"), today)
	for c in frappe.get_all("AMC Contract", filters={"docstatus": ["<", 2]}, fields=["name", "start_date", "end_date"]):
		status, days = logic.contract_status(getdate(c.start_date), getdate(c.end_date), today)
		frappe.db.set_value(
			"AMC Contract", c.name, {"contract_status": status or None, "days_left": days if days is not None else 0}, update_modified=False
		)
	frappe.db.sql(
		"update `tabAMC Visit` set is_overdue = if(status = 'Planned' and planned_date < %s, 1, 0)", (today,)
	)


def collect_alerts(today):
	"""Everything that needs attention, as dicts. 'mail' is True when the daily rules send it today."""
	alerts = []
	contracts = frappe.get_all(
		"AMC Contract",
		filters={"docstatus": 1},
		fields=["name", "vendor", "end_date", "remind_before_days", "assets_summary", "renewal_status"],
	)
	for c in contracts:
		days = (getdate(c.end_date) - today).days
		if days < 0:
			continue
		rem = c.remind_before_days if c.remind_before_days is not None else 60
		if days <= rem:
			steps = logic.reminder_steps(rem)
			alerts.append({"kind": "Contract ending", "doctype": "AMC Contract", "name": c.name, "text": "{0} · {1}".format(c.vendor, c.assets_summary or ""), "date": c.end_date, "days": days, "mail": days in steps})
	for a in frappe.get_all("AMC Asset", filters={"warranty_end": ["is", "set"]}, fields=["name", "asset_name", "warranty_provider", "warranty_end"]):
		days = (getdate(a.warranty_end) - today).days
		if 0 <= days <= logic.WARRANTY_DAYS:
			alerts.append({"kind": "Warranty ending", "doctype": "AMC Asset", "name": a.name, "text": "{0} · {1}".format(a.asset_name, a.warranty_provider or ""), "date": a.warranty_end, "days": days, "mail": days in logic.WARRANTY_REMIND_STEPS})
	has_other = frappe.get_meta("AMC Visit").has_field("visit_type_other")
	visits = frappe.get_all(
		"AMC Visit", filters={"status": "Planned"}, fields=["name", "asset", "visit_type", "planned_date"] + (["visit_type_other"] if has_other else [])
	)
	for v in visits:
		days = (getdate(v.planned_date) - today).days
		if days < 0:
			alerts.append({"kind": "Overdue visit", "doctype": "AMC Visit", "name": v.name, "text": "{0} · {1}".format(v.asset, v.get("visit_type_other") if v.visit_type == "Other" and v.get("visit_type_other") else v.visit_type), "date": v.planned_date, "days": days, "mail": True})
		elif days <= logic.VISIT_ALERT_DAYS:
			alerts.append({"kind": "Visit in next 3 days", "doctype": "AMC Visit", "name": v.name, "text": "{0} · {1}".format(v.asset, v.get("visit_type_other") if v.visit_type == "Other" and v.get("visit_type_other") else v.visit_type), "date": v.planned_date, "days": days, "mail": True})
	return alerts


def manager_users():
	users = frappe.get_all("Has Role", filters={"role": "AMC Manager", "parenttype": "User"}, pluck="parent")
	if not users:
		return []
	return frappe.get_all("User", filters={"name": ["in", users], "enabled": 1}, pluck="name")


def _when(a):
	if a["days"] < 0:
		return "{0} day(s) overdue".format(-a["days"])
	return "today" if a["days"] == 0 else "{0} day(s) left".format(a["days"])


def build_notification(to_send, today):
	"""The subject and the HTML body for the alerts that are mailed today (no database writes)."""
	subject = "AMC Tracker: {0} item(s) need attention ({1})".format(len(to_send), formatdate(today))
	order = ["Overdue visit", "Visit in next 3 days", "Contract ending", "Warranty ending"]
	body = []
	for kind in order:
		rows = [a for a in to_send if a["kind"] == kind]
		if not rows:
			continue
		items = "".join(
			"<li>{0} — {1} ({2}) <i>{3}</i></li>".format(escape_html(a["text"]), _when(a), formatdate(a["date"]), escape_html(a["name"]))
			for a in rows
		)
		body.append("<b>{0}</b><ul>{1}</ul>".format(kind, items))
	return subject, "".join(body)


def notify_managers(today):
	"""One system notification (and the e-mail Frappe sends for it, per each user's notification settings) per manager per day."""
	to_send = [a for a in collect_alerts(today) if a["mail"]]
	users = manager_users()
	if not to_send or not users:
		return 0
	subject, html = build_notification(to_send, today)
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	fresh = [u for u in users if not frappe.db.exists("Notification Log", {"for_user": u, "subject": subject})]
	if fresh:
		enqueue_create_notification(fresh, {"type": "Alert", "subject": subject, "email_content": html})
	return len(fresh)
