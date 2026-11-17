from datetime import datetime
import unittest

from nfl_atd_morning_watchlist import render


NOW = datetime.fromisoformat("2026-11-16T09:00:00-06:00")


def slate(players=None):
    return {"sport": "NFL ATD", "provider": "Kalshi",
            "date_central": "2026-11-16", "paper_only": True,
            "orders_placed": 0, "fixtures": [{
                "fixture_id": "2026111601", "fixture_verified": True,
                "away": "GB", "home": "NYG",
                "start_central": "2026-11-16T19:15:00-06:00",
                "players": players or [{
                    "player_id": "p1", "name": "Player One",
                    "inactive_checked": True, "market_identity_verified": True,
                    "contract": "KXNFLANYTD-GB-NYG-P1",
                }],
            }]}


class NFLMorningWatchlistTest(unittest.TestCase):
    def test_active_player_contract_and_entry_window(self):
        field = render(slate(), NOW)["embeds"][0]["fields"][0]["value"]
        self.assertIn("KXNFLANYTD-GB-NYG-P1", field)
        self.assertIn("T-90", field)
        self.assertIn("[PAPER WATCHLIST]", render(slate(), NOW)["embeds"][0]["title"])

    def test_zero_games_still_renders_complete_slate(self):
        data = slate()
        data["fixtures"] = []
        self.assertIsNone(render(data, NOW))

    def test_unmatched_and_inactive_are_fail_closed(self):
        player = {"player_id": "p1", "name": "Player One",
                  "inactive_checked": True, "market_identity_verified": False,
                  "contract": ""}
        self.assertIn("UNMATCHED/NO VERIFIED CONTRACT",
                      render(slate([player]), NOW)["embeds"][0]["fields"][0]["value"])
        player["inactive_checked"] = False
        with self.assertRaises(ValueError):
            render(slate([player]), NOW)

    def test_invalid_contract_is_rejected(self):
        data = slate()
        data["fixtures"][0]["players"][0]["contract"] = "KXNHLGAME-NOT-NFL"
        with self.assertRaises(ValueError):
            render(data, NOW)


if __name__ == "__main__":
    unittest.main()
