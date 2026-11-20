# Copyright (c) 2026, Dux Digitech and contributors
# For license information, please see license.txt

"""Excel download for the page's report tables: the page sends the table as shown, this returns an .xlsx file (base64)."""

import base64
import re

import frappe
from frappe import _
from frappe.utils.xlsxutils import make_xlsx

MAX_ROWS = 20000


@frappe.whitelist(methods=["POST"])
def make_xlsx_file(title, rows):
	frappe.has_permission("AMC Asset", "read", throw=True)
	data = frappe.parse_json(rows) or []
	if not isinstance(data, list) or len(data) > MAX_ROWS:
		frappe.throw(_("Too many rows for one Excel file."))
	data = [["" if v is None else v for v in row] if isinstance(row, list) else [row] for row in data]
	sheet = re.sub(r"[\[\]:*?/\\]+", " ", title or "Report").strip()[:31] or "Report"
	return base64.b64encode(make_xlsx(data, sheet).getvalue()).decode()
