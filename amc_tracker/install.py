# Copyright (c) 2026, Dux Digitech and contributors
# For license information, please see license.txt

import frappe

# "Maintenance User" is the standard ERPNext role and already exists.
ROLES = ("AMC Manager", "Campus Viewer")


def before_install():
	ensure_roles()


def after_install():
	ensure_roles()


def ensure_roles():
	"""Roles are created before the doctypes that use them are synced. Safe to run again."""
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)
	if not frappe.db.exists("Role", "Maintenance User"):
		frappe.get_doc({"doctype": "Role", "role_name": "Maintenance User", "desk_access": 1}).insert(ignore_permissions=True)
