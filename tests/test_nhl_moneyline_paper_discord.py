"""Offline mobile moneyline card colors, accuracy and routing safety tests."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nhl_moneyline_paper_discord import render, route, BLUE, TEAL, GREEN, RED, _tier

NOW = datetime(2026, 11, 15, 21, 30, tzinfo=timezone.utc)


def example(stage, status=None):
    settled = stage == "results"
    start = NOW - timedelta(hours=3) if settled else NOW + timedelta(minutes=3)
    entry = start - timedelta(minutes=53)
    close = start - timedelta(minutes=1)
    return {
        "schema_version": "nhl-kalshi-moneyline-paper-v1",
        "market_series": "KXNHLGAME",
        "paper_trade": True, "orders_placed": 0,
        "run_mode": "verified_prospective",
        "source_repository": "stelladeecoder/statrally-even-odd-models",
        "stage": stage, "generated_at_utc": (NOW-timedelta(minutes=2)).isoformat(),
        "games": [{
            "game_id": "fixture-1",
            "fixture": "Away @ Home", "selected_team": "Home",
            "market_ticker": "KXNHLGAME-EXAMPLE-HOME",
            "fixture_verified": True, "market_identity_verified": True,
            "model_probability": .68,
            "game_start_utc": start.isoformat(),
            "entry_observed_utc": entry.isoformat(),
            "minutes_before_start": 53,
            "status": status or ("SETTLED" if settled else "PAPER_TRADE"),
            "ask_dollars": ".55", "fee_dollars": ".02",
            "fee_verified": True, "depth_contracts": "6",
            "net_ev_on_cost": ".19", "band": "short_favorite",
            "closing_observed_utc": close.isoformat(),
            "closing_ask_dollars": ".61", "ask_price_move_dollars": ".06",
            "settlement_verified": True, "paper_win": True,
            "paper_profit_dollars": ".43",
        }],
        "cumulative": {"settled_paper_games": 1, "wins": 1,
                       "losses": 0, "net_paper_roi": ".75"},
    }


class TestMoneylineDiscord(unittest.TestCase):
    def test_routes_are_explicit(self):
        env = {
            "STATRALLY_NHL_WATCHLIST_WEBHOOK": "watch",
            "STATRALLY_NHL_PICKS_WEBHOOK": "picks",
            "STATRALLY_NHL_RESULTS_WEBHOOK": "results",
        }
        self.assertEqual(route("watchlist", env), "watch")
        self.assertEqual(route("picks", env), "picks")
        self.assertEqual(route("results", env), "results")
        env["STATRALLY_NHL_RESULTS_WEBHOOK"] = "picks"
        with self.assertRaises(ValueError):
            route("picks", env)

    def test_watchlist_no_bet_blue_and_full_fields(self):
        r = example("watchlist", "NO_BET")
        payload = render(r, "watchlist", now=NOW)[0]["embeds"][0]
        self.assertEqual(payload["color"], BLUE)
        for label in ("Model Win Prob", "Kalshi Executable Ask",
                      "Fee:", "Orderbook Depth", "Net EV", "Odds Tier",
                      "NO BET", "Away @ Home"):
            self.assertIn(label, payload["description"])

    def test_picks_exclude_no_bets(self):
        r = example("picks", "NO_BET")
        payload = render(r, "picks", now=NOW)[0]["embeds"][0]
        self.assertIn("No qualified", payload["description"])
        self.assertEqual(payload["color"], TEAL)

    def test_picks_teal_tier_and_thresholds(self):
        payload = render(example("picks"), "picks", now=NOW)[0]["embeds"][0]
        self.assertEqual(payload["color"], TEAL)
        desc = payload["description"]
        self.assertIn("[PAPER TRADE]", desc)
        self.assertIn("Short favorite", desc)
        self.assertIn("+5.00%", desc)
        self.assertIn("6 contracts", desc)

    def test_fee_unverified_paper_pick_rejected(self):
        report = example("picks")
        report["games"][0]["fee_verified"] = False
        with self.assertRaises(ValueError):
            render(report, "picks", now=NOW)

    def test_no_bet_fee_unverified_hides_ev(self):
        r = example("watchlist", "NO_BET")
        r["games"][0].update(fee_verified=False, fee_dollars=None, net_ev_on_cost=None)
        text = render(r, "watchlist", now=NOW)[0]["embeds"][0]["description"]
        self.assertIn("Fee:** Unverified", text)
        self.assertIn("EV (post-fee):** UNKNOWN", text)

    def test_unverified_ev_rejected(self):
        r = example("watchlist", "NO_BET")
        r["games"][0]["fee_verified"] = False
        with self.assertRaises(ValueError):
            render(r, "watchlist", now=NOW)

    def test_results_win_green_with_clv_and_scorecard(self):
        cards = render(example("results"), "results", now=NOW)
        first = cards[0]["embeds"][0]
        score = cards[-1]["embeds"][0]
        self.assertEqual(first["color"], GREEN)
        self.assertIn("WIN", first["title"])
        self.assertIn("Entry Ask", first["description"])
        self.assertIn("Puck-Drop Closing Ask", first["description"])
        self.assertIn("CLV Proxy", first["description"])
        self.assertIn("Post-Fee Paper P&L", first["description"])
        self.assertIn("150 minimum", score["description"])
        self.assertIn("250 extended", score["description"])
        self.assertIn("1/150", score["description"])
        self.assertEqual(score["color"], BLUE)

    def test_results_loss_red(self):
        r = example("results")
        r["games"][0].update(paper_win=False, paper_profit_dollars="-.57")
        cards = render(r, "results", now=NOW)
        self.assertEqual(cards[0]["embeds"][0]["color"], RED)
        self.assertIn("LOSS", cards[0]["embeds"][0]["title"])

    def test_results_require_verified_outcome(self):
        r = example("results")
        del r["games"][0]["paper_win"]
        with self.assertRaises(ValueError):
            render(r, "results", now=NOW)

    def test_wrong_closing_window_rejected(self):
        r = example("results")
        r["games"][0]["closing_observed_utc"] = (
            NOW - timedelta(hours=3) + timedelta(minutes=1)).isoformat()
        with self.assertRaises(ValueError):
            render(r, "results", now=NOW)

    def test_ev_mismatch_rejected(self):
        r = example("picks")
        r["games"][0]["net_ev_on_cost"] = ".45"
        with self.assertRaises(ValueError):
            render(r, "picks", now=NOW)

    def test_wrong_band_rejected(self):
        r = example("picks")
        r["games"][0]["band"] = "underdog"
        with self.assertRaises(ValueError):
            render(r, "picks", now=NOW)

    def test_wrong_source_rejected(self):
        r = example("watchlist")
        r["paper_trade"] = False
        with self.assertRaises(ValueError):
            render(r, "watchlist", now=NOW)

    def test_duplicate_games_rejected(self):
        r = example("watchlist")
        r["games"].append(dict(r["games"][0]))
        with self.assertRaises(ValueError):
            render(r, "watchlist", now=NOW)

    def test_max_one_embed_per_mobile_card(self):
        r = example("watchlist")
        row = dict(r["games"][0])
        row["game_id"] = "fixture-2"
        r["games"].append(row)
        messages = render(r, "watchlist", now=NOW)
        self.assertEqual(len(messages), 2)
        self.assertTrue(all(len(m["embeds"]) == 1 for m in messages))


if __name__ == "__main__":
    unittest.main()
