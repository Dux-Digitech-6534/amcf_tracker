# Copyright (c) 2026, Dux Digitech and contributors
# For license information, please see license.txt

"""Date and money rules for AMC Tracker.

Nothing in this file imports Frappe, so the rules can be unit tested anywhere
(python -m unittest amc_tracker.tests.test_logic) and every controller uses the same numbers.
"""

import calendar
from datetime import date

# A contract counts as "Expiring" when this many days or fewer are left.
EXPIRING_DAYS = 90
# A warranty counts as "Expiring" (and is mailed) inside this many days.
WARRANTY_DAYS = 60
# After the first reminder (at remind_before_days) a contract is mailed again at these days left.
REMIND_STEPS = (30, 7, 0)
# Warranty reminders use these days left.
WARRANTY_REMIND_STEPS = (60, 30, 7, 0)
# Planned visits inside this many days are mailed.
VISIT_ALERT_DAYS = 3

FREQUENCY_MONTHS = {"Monthly": 1, "Quarterly": 3, "Half yearly": 6, "Yearly": 12}

# Naming series per asset type. To add a type: add it here and to the options of AMC Asset > Asset type, then migrate.
ASSET_TYPE_PREFIX = {
	"Lift / Elevator": "LFT",
	"RO / Water Treatment": "RO",
	"DG Set": "DG",
	"HVAC / AC": "AC",
	"Fire Fighting": "FIRE",
	"CCTV / Security": "CCTV",
	"Electrical / Transformer": "ELE",
	"UPS / Inverter": "UPS",
	"Pumps": "PMP",
	"IT / Networking": "IT",
}
DEFAULT_PREFIX = "AST"


def prefix_for(asset_type):
	return ASSET_TYPE_PREFIX.get(asset_type or "", DEFAULT_PREFIX)


def add_months(d, n):
	"""d plus n months; a day that does not exist in the target month moves to its last day (31 Jan + 1 month = 28 Feb)."""
	index = d.year * 12 + (d.month - 1) + n
	year, month = divmod(index, 12)
	month += 1
	return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def contract_status(start, end, today):
	"""Return (status, days_left) for a contract period. days_left counts to the end date and is negative once ended."""
	if not start or not end:
		return "", None
	days = (end - today).days
	if start > today:
		return "Upcoming", days
	if days < 0:
		return "Expired", days
	if days <= EXPIRING_DAYS:
		return "Expiring", days
	return "Active", days


def warranty_status(end, today):
	if not end:
		return "Not recorded"
	days = (end - today).days
	if days < 0:
		return "Expired"
	if days <= WARRANTY_DAYS:
		return "Expiring"
	return "Under warranty"


def asset_amc_state(contracts, today):
	"""contracts: submitted contracts that cover one asset, as dicts with name, start, end.

	Returns (contract name, status, days left): the running contract if there is one, else the next
	upcoming one, else the latest one that ended, else No AMC.
	"""
	rows = []
	for c in contracts:
		status, days = contract_status(c["start"], c["end"], today)
		rows.append((c, status, days))
	rows.sort(key=lambda r: r[0]["end"], reverse=True)
	for c, status, days in rows:
		if status in ("Active", "Expiring"):
			return c["name"], status, days
	upcoming = sorted((r for r in rows if r[1] == "Upcoming"), key=lambda r: r[0]["start"])
	if upcoming:
		c, status, days = upcoming[0]
		return c["name"], status, days
	if rows:
		c, status, days = rows[0]
		return c["name"], "Expired", days
	return "", "No AMC", None


def schedule_dates(start, end, frequency, today, include_past=False):
	"""Visit dates from start to end every interval. Past dates are skipped unless include_past is set."""
	months = FREQUENCY_MONTHS.get(frequency)
	if not months:
		raise ValueError("Visit frequency must be Monthly, Quarterly, Half yearly or Yearly to make a schedule.")
	if not start or not end:
		raise ValueError("Start date and end date are required.")
	out = []
	i = 0
	while True:
		d = add_months(start, i * months)
		if d > end:
			break
		if include_past or d >= today:
			out.append(d)
		i += 1
	return out


def renewal_values(start, end, value_excl_gst, escalation_percent):
	"""New start, new end and the escalated value for a renewal: both dates move exactly one year."""
	factor = 1 + (escalation_percent or 0) / 100.0
	return add_months(start, 12), add_months(end, 12), round((value_excl_gst or 0) * factor, 2)


def total_incl_gst(value_excl_gst, gst_percent):
	return round((value_excl_gst or 0) * (1 + (gst_percent or 0) / 100.0), 2)


def cost_of_ownership(purchase_cost, contracts, visit_charges):
	"""contracts: list of (total incl. GST, number of assets covered). A contract covering several assets is split equally."""
	amc = sum((total or 0) / max(1, count or 1) for total, count in contracts)
	amc = round(amc, 2)
	purchase = round(purchase_cost or 0, 2)
	visits = round(visit_charges or 0, 2)
	return {"purchase": purchase, "amc": amc, "visits": visits, "total": round(purchase + amc + visits, 2)}


def reminder_steps(remind_before_days):
	"""Days left on which a contract mail goes out: the first reminder, then 30, 7 and 0."""
	steps = set(REMIND_STEPS)
	if remind_before_days is not None and remind_before_days >= 0:
		steps.add(int(remind_before_days))
	return sorted(steps, reverse=True)


def contract_reminder_due(days_left, remind_before_days):
	return days_left is not None and days_left in reminder_steps(remind_before_days)


def next_reminder(days_left, steps):
	"""The next days-left value at which a mail will go out, or None."""
	later = [s for s in steps if days_left is not None and s < days_left]
	return max(later) if later else None


def is_overdue(status, planned_date, today):
	return status == "Planned" and planned_date is not None and planned_date < today
