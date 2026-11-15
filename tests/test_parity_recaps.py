import unittest
from datetime import date

from parity_recaps import payload, periods


class ParityRecapTests(unittest.TestCase):
    def test_week_runs_sunday_through_saturday(self):
        expected = (date(2026, 11, 8), date(2026, 11, 14))
        self.assertEqual(periods(date(2026, 11, 14))["weekly"], expected)
        self.assertEqual(periods(date(2026, 11, 15))["weekly"], expected)

    def test_combined_accuracy_includes_stars_and_excludes_pending(self):
        day = date(2026, 11, 14)
        rows = [
            {"day": day, "sport": "soccer", "starred": False, "correct": False},
            {"day": day, "sport": "hockey", "starred": True, "correct": True},
            {"day": day, "sport": "hockey", "starred": True, "correct": None},
        ]
        text = payload("daily", day, day, rows)["embeds"][0]["description"]
        overall, stars = text.split("VERY HIGH MODEL PROBABILITY")
        self.assertIn("Combined** · 1 correct / 2 graded · **50.0%** · 1 pending", overall)
        self.assertIn("Soccer** · 0 correct / 1 graded", overall)
        self.assertIn("NHL** · 1 correct / 1 graded", overall)
        self.assertIn("Combined** · 1 correct / 1 graded · **100.0%** · 1 pending", stars)

    def test_calendar_uses_combined_daily_record_and_no_yellow_cells(self):
        day = date(2026, 11, 14)
        rows = [{"day": day, "sport": "soccer", "starred": False, "correct": True}]
        monthly = payload("monthly", day.replace(day=1), day, rows)["embeds"][0]["description"]
        embed = payload("monthly", day.replace(day=1), day, rows)["embeds"][0]
        self.assertEqual(embed["image"]["url"], "attachment://statrally-evenodd-monthly-calendar.png")
        self.assertNotIn("```", monthly)
        self.assertNotIn("🟨", monthly.split("VERY HIGH MODEL PROBABILITY")[0])
        self.assertNotIn("Calendar", payload("weekly", day, day, rows)["embeds"][0]["description"])
