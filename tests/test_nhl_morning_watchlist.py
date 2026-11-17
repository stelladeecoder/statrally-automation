from datetime import datetime
import unittest

from nhl_morning_watchlist import render


class MorningWatchlistTest(unittest.TestCase):
    def test_zero_pick_slate_renders_unmatched_fixture(self):
        now = datetime.fromisoformat("2026-11-16T09:00:00-06:00")
        data = {"sport":"NHL Moneyline","provider":"Kalshi","date_central":"2026-11-16",
                "paper_only":True,"orders_placed":0,"fixtures":[
                    {"fixture_id":"2026020001","away":"VAN","home":"UTA",
                     "start_central":"2026-11-16T20:30:00-06:00",
                     "market_identity_verified":False,"contracts":[]}]}
        embed = render(data, now)["embeds"][0]
        self.assertIn("[PAPER WATCHLIST]", embed["title"])
        self.assertIn("07:30 PM–07:45 PM CST", embed["fields"][0]["value"])
        self.assertIn("No verified Kalshi contract", embed["fields"][0]["value"])
        data["fixtures"][0]["contracts"] = ["KXNHLGAME-TEST-VAN"]
        with self.assertRaises(ValueError):
            render(data, now)
        data["fixtures"] = []
        self.assertIn("No NHL games scheduled", render(data, now)["embeds"][0]["description"])
        data["date_central"] = "2026-11-15"
        with self.assertRaises(ValueError):
            render(data, now)
