"""Offline Moneyline Discord route and signal validation tests."""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nhl_moneyline_paper_discord import render, route

NOW = datetime(2026, 11, 15, 21, 30, tzinfo=timezone.utc)
def example(stage, status=None):
    result = {
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
            "entry_observed_utc": (NOW-timedelta(minutes=3)).isoformat(),
            "minutes_before_start": 53,
            "status": status or ("SETTLED" if stage=="results" else "PAPER_TRADE"),
            "ask_dollars": ".55", "fee_dollars": ".02",
            "fee_verified": True, "depth_contracts": "6",
            "net_ev_on_cost": ".19", "band": "short_favorite",
            "closing_observed_utc": NOW.isoformat(),
            "closing_ask_dollars": ".61", "ask_price_move_dollars": ".06",
            "settlement_verified": True, "paper_profit_dollars": ".43",
        }],
        "cumulative": {"settled_paper_games": 1, "net_paper_roi": ".75"},
    }
    return result


class TestMoneylineDiscord(unittest.TestCase):
    def test_routes_are_explicit(self):
        e = {
            "STATRALLY_NHL_WATCHLIST_WEBHOOK": "watch",
            "STATRALLY_NHL_PICKS_WEBHOOK": "picks",
            "STATRALLY_NHL_RESULTS_WEBHOOK": "results",
        }
        self.assertEqual(route("watchlist", e), "watch")
        self.assertEqual(route("picks", e), "picks")
        self.assertEqual(route("results", e), "results")
        e["STATRALLY_NHL_RESULTS_WEBHOOK"] = "picks"
        with self.assertRaises(ValueError):
            route("picks", e)

    def test_watchlist_includes_no_bets(self):
        report = example("watchlist", "NO_BET")
        payloads = render(report,"watchlist",now=NOW)
        self.assertIn("NO BET", payloads[0]["embeds"][0]["description"])

    def test_picks_exclude_no_bets(self):
        r = example("picks","NO_BET")
        self.assertIn("No qualified",render(r,"picks",now=NOW)[0]["embeds"][0]["description"])

    def test_picks_show_verified_tiers(self):
        payloads=render(example("picks"),"picks",now=NOW)
        desc=payloads[0]["embeds"][0]["description"]
        self.assertIn("PAPER TRADE",desc)
        self.assertIn("Short favorite",desc)
        self.assertIn("+5.00%",desc)

    def test_fees_not_verified_refuse_paper_pick(self):
        report=example("picks")
        report["games"][0]["fee_verified"]=False
        with self.assertRaises(ValueError):
            render(report,"picks",now=NOW)

    def test_results_track_sample(self):
        text=render(example("results"),"results",now=NOW)[0]["embeds"][0]["description"]
        self.assertIn("1 settled paper games",text)
        self.assertIn("proxy",text)

    def test_wrong_source_refused(self):
        report=example("watchlist")
        report["paper_trade"]=False
        with self.assertRaises(ValueError):
            render(report,"watchlist",now=NOW)

    def test_duplicate_games_refused(self):
        report=example("watchlist")
        report["games"].append(dict(report["games"][0]))
        with self.assertRaises(ValueError):
            render(report,"watchlist",now=NOW)


if __name__=="__main__":
    unittest.main()
