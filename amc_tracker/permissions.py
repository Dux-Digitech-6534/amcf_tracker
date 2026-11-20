# Copyright (c) 2026, Dux Digitech and contributors
# For license information, please see license.txt

"""Campus limits for contracts and visits.

An asset's campus is a Company link, so a User Permission on Company limits assets by itself. Contracts and visits
have no Company field, so they are limited here through the assets they cover. AMC Manager and System Manager see everything.
"""

import frappe

UNLIMITED_ROLES = {"System Manager", "AMC Manager"}


def allowed_companies(user=None):
	"""None when the user has no campus limit, else the list of Companies the user may see."""
	user = user or frappe.session.user
	if user == "Administrator" or UNLIMITED_ROLES & set(frappe.get_roles(user)):
		return None
	companies = frappe.get_all("User Permission", filters={"user": user, "allow": "Company"}, pluck="for_value")
	return companies or None


def _in_list(companies):
	return ", ".join(frappe.db.escape(c) for c in companies)


def visit_query(user=None):
	companies = allowed_companies(user)
	if companies is None:
		return ""
	return "`tabAMC Visit`.`asset` in (select name from `tabAMC Asset` where campus in ({0}))".format(_in_list(companies))


def contract_query(user=None):
	companies = allowed_companies(user)
	if companies is None:
		return ""
	return (
		"exists (select 1 from `tabAMC Contract Asset` ca inner join `tabAMC Asset` a on a.name = ca.asset "
		"where ca.parent = `tabAMC Contract`.name and ca.parenttype = 'AMC Contract' and a.campus in ({0}))"
	).format(_in_list(companies))


def visit_has_permission(doc, ptype=None, user=None, **kwargs):
	companies = allowed_companies(user)
	if companies is None:
		return True
	return frappe.db.get_value("AMC Asset", doc.asset, "campus") in companies


def contract_has_permission(doc, ptype=None, user=None, **kwargs):
	companies = allowed_companies(user)
	if companies is None:
		return True
	campuses = {
		frappe.db.get_value("AMC Asset", row.asset, "campus") for row in (doc.get("assets") or []) if row.asset
	}
	return bool(campuses & set(companies))
