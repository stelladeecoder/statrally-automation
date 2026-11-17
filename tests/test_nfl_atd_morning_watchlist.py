import unittest
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_atd_morning_watchlist import render


class NFLAtdMorningWatchlistTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime.fromisoformat("2026-11-22T09:00:00-06:00")

    def data(self):
        return {
            "schema": "nfl-atd-shadow-live-v2",
            "sport": "nfl",
            "market_type": "atd",
            "paper_only": True,
            "orders_placed": 0,
            "discord_posts": 0,
            "fixtures": [{
                "fixture_id": "2026w11-MIA-BUF",
                "kickoff_utc": "2026-11-22T18:00:00Z",
                "players": [{
                    "ticker": "KXNFLANYTD-26NOV22BUF-PLAYER",
                    "player_id": "p1",
                    "full_name": "Example Player",
                    "identity_verified": True,
                    "official_active_verified": True,
                }],
            }],
        }

    def test_renders_verified_active_contract_and_t90_window(self):
        embed = render(self.data(), self.now)["embeds"][0]
        self.assertIn("[PAPER WATCHLIST]", embed["title"])
        self.assertIn("10:30 AM-11:00 AM CST", embed["fields"][0]["value"])
        self.assertIn("KXNFLANYTD-", embed["fields"][0]["value"])

    def test_zero_qualifying_players_still_posts_full_fixture(self):
        data = self.data()
        data["fixtures"][0]["players"][0]["official_active_verified"] = False
        payload = render(data, self.now)
        self.assertIn("No verified active NFL ATD contract",
                      payload["embeds"][0]["fields"][0]["value"])

    def test_rejects_non_kalshi_or_live_orders(self):
        data = self.data()
        data["fixtures"][0]["players"][0]["ticker"] = "POLY-TEST"
        with self.assertRaises(ValueError):
            render(data, self.now)
        data = self.data()
        data["orders_placed"] = 1
        with self.assertRaises(ValueError):
            render(data, self.now)


if __name__ == "__main__":
    unittest.main()
