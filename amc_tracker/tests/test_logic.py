# Copyright (c) 2026, Dux Digitech and contributors
# For license information, please see license.txt

"""Unit tests for the AMC rules. They need no site and no database:

	python -m unittest amc_tracker.tests.test_logic
"""

import unittest
from datetime import date, timedelta

from amc_tracker import logic

TODAY = date(2026, 11, 18)


def d(n):
	return TODAY + timedelta(days=n)


class TestStatusBoundaries(unittest.TestCase):
	def status(self, days_to_end):
		return logic.contract_status(date(2020, 1, 1), d(days_to_end), TODAY)

	def test_expired_the_day_after_end(self):
		self.assertEqual(self.status(-1), ("Expired", -1))

	def test_ends_today_is_still_running(self):
		self.assertEqual(self.status(0), ("Expiring", 0))

	def test_thirty_days(self):
		self.assertEqual(self.status(30), ("Expiring", 30))
		self.assertEqual(self.status(31), ("Expiring", 31))

	def test_ninety_days(self):
		self.assertEqual(self.status(90), ("Expiring", 90))
		self.assertEqual(self.status(91), ("Active", 91))

	def test_upcoming(self):
		self.assertEqual(logic.contract_status(d(5), d(400), TODAY), ("Upcoming", 400))

	def test_missing_dates(self):
		self.assertEqual(logic.contract_status(None, d(5), TODAY), ("", None))

	def test_warranty(self):
		self.assertEqual(logic.warranty_status(None, TODAY), "Not recorded")
		self.assertEqual(logic.warranty_status(d(-1), TODAY), "Expired")
		self.assertEqual(logic.warranty_status(d(0), TODAY), "Expiring")
		self.assertEqual(logic.warranty_status(d(60), TODAY), "Expiring")
		self.assertEqual(logic.warranty_status(d(61), TODAY), "Under warranty")

	def test_asset_state(self):
		running = {"name": "A", "start": date(2026, 1, 1), "end": d(200)}
		ended = {"name": "B", "start": date(2025, 1, 1), "end": date(2025, 12, 31)}
		later = {"name": "C", "start": d(10), "end": d(375)}
		self.assertEqual(logic.asset_amc_state([], TODAY), ("", "No AMC", None))
		self.assertEqual(logic.asset_amc_state([ended], TODAY)[1], "Expired")
		self.assertEqual(logic.asset_amc_state([ended, later], TODAY)[:2], ("C", "Upcoming"))
		self.assertEqual(logic.asset_amc_state([ended, running, later], TODAY), ("A", "Active", 200))


class TestMonthMath(unittest.TestCase):
	def test_month_end_clamps(self):
		self.assertEqual(logic.add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
		self.assertEqual(logic.add_months(date(2026, 1, 31), 2), date(2026, 3, 31))
		self.assertEqual(logic.add_months(date(2028, 2, 29), 12), date(2029, 2, 28))

	def test_crossing_year(self):
		self.assertEqual(logic.add_months(date(2026, 11, 15), 3), date(2027, 2, 15))
		self.assertEqual(logic.add_months(date(2026, 12, 1), 12), date(2027, 12, 1))


class TestSchedule(unittest.TestCase):
	def test_monthly_whole_year(self):
		dates = logic.schedule_dates(date(2026, 1, 1), date(2026, 12, 31), "Monthly", date(2026, 1, 1))
		self.assertEqual(len(dates), 12)
		self.assertEqual(dates[0], date(2026, 1, 1))
		self.assertEqual(dates[-1], date(2026, 12, 1))

	def test_past_dates_are_skipped(self):
		dates = logic.schedule_dates(date(2026, 1, 1), date(2026, 12, 31), "Monthly", TODAY)
		self.assertEqual(dates, [date(2026, 12, 1)])

	def test_past_dates_can_be_included(self):
		dates = logic.schedule_dates(date(2026, 1, 1), date(2026, 12, 31), "Monthly", TODAY, include_past=True)
		self.assertEqual(len(dates), 12)

	def test_quarterly_and_no_duplicates(self):
		dates = logic.schedule_dates(date(2026, 5, 3), date(2027, 5, 2), "Quarterly", date(2026, 5, 3))
		self.assertEqual(dates, [date(2026, 5, 3), date(2026, 8, 3), date(2026, 11, 3), date(2027, 2, 3)])
		self.assertEqual(len(dates), len(set(dates)))

	def test_end_date_is_included(self):
		dates = logic.schedule_dates(date(2026, 1, 1), date(2026, 3, 1), "Monthly", date(2026, 1, 1))
		self.assertEqual(dates[-1], date(2026, 3, 1))

	def test_on_call_has_no_schedule(self):
		with self.assertRaises(ValueError):
			logic.schedule_dates(date(2026, 1, 1), date(2026, 12, 31), "On call", TODAY)
		with self.assertRaises(ValueError):
			logic.schedule_dates(date(2026, 1, 1), date(2026, 12, 31), "", TODAY)


class TestRenewal(unittest.TestCase):
	def test_dates_move_one_year_and_value_escalates(self):
		start, end, value = logic.renewal_values(date(2026, 5, 3), date(2027, 5, 2), 31250, 10)
		self.assertEqual((start, end, value), (date(2027, 5, 3), date(2028, 5, 2), 34375.0))

	def test_no_escalation(self):
		start, end, value = logic.renewal_values(date(2026, 1, 1), date(2026, 12, 31), 40077, None)
		self.assertEqual((start, end, value), (date(2027, 1, 1), date(2027, 12, 31), 40077.0))

	def test_total_incl_gst(self):
		self.assertEqual(logic.total_incl_gst(40077, 18), 47290.86)
		self.assertEqual(logic.total_incl_gst(80000, 18), 94400.0)
		self.assertEqual(logic.total_incl_gst(None, 18), 0)


class TestCostOfOwnership(unittest.TestCase):
	def test_shared_contract_is_split_equally(self):
		coo = logic.cost_of_ownership(0, [(94400, 2)], 4500)
		self.assertEqual(coo, {"purchase": 0, "amc": 47200.0, "visits": 4500, "total": 51700.0})

	def test_purchase_plus_two_contracts(self):
		coo = logic.cost_of_ownership(186500, [(47292.86, 1), (36875, 1)], 7000)
		self.assertEqual(coo["amc"], 84167.86)
		self.assertEqual(coo["total"], 277667.86)

	def test_nothing_recorded(self):
		self.assertEqual(logic.cost_of_ownership(None, [], None)["total"], 0)


class TestReminders(unittest.TestCase):
	def test_steps_include_first_reminder(self):
		self.assertEqual(logic.reminder_steps(60), [60, 30, 7, 0])
		self.assertEqual(logic.reminder_steps(45), [45, 30, 7, 0])
		self.assertEqual(logic.reminder_steps(30), [30, 7, 0])

	def test_due_only_on_step_days(self):
		self.assertTrue(logic.contract_reminder_due(60, 60))
		self.assertTrue(logic.contract_reminder_due(30, 60))
		self.assertTrue(logic.contract_reminder_due(0, 60))
		self.assertFalse(logic.contract_reminder_due(43, 60))
		self.assertFalse(logic.contract_reminder_due(None, 60))

	def test_next_reminder(self):
		self.assertEqual(logic.next_reminder(43, [60, 30, 7, 0]), 30)
		self.assertEqual(logic.next_reminder(0, [60, 30, 7, 0]), None)

	def test_overdue(self):
		self.assertTrue(logic.is_overdue("Planned", d(-1), TODAY))
		self.assertFalse(logic.is_overdue("Planned", TODAY, TODAY))
		self.assertFalse(logic.is_overdue("Done", d(-30), TODAY))


class TestNaming(unittest.TestCase):
	def test_prefixes(self):
		self.assertEqual(logic.prefix_for("Lift / Elevator"), "LFT")
		self.assertEqual(logic.prefix_for("DG Set"), "DG")
		self.assertEqual(logic.prefix_for("Lab Equipment"), "AST")
		self.assertEqual(logic.prefix_for("Other"), "AST")
		self.assertEqual(logic.prefix_for(None), "AST")


if __name__ == "__main__":
	unittest.main()
