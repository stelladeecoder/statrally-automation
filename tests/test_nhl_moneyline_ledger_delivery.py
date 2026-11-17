"""Offline regression tests for NHL paper ledger delivery safety."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import nhl_moneyline_ledger_delivery as delivery


class PaperDeliveryTests(unittest.TestCase):
    def test_discord_send_requires_numeric_200_receipt_and_standard_user_agent(self):
        class Response:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return b'{"id":"123456789012345678"}'

        requests = []
        message_id = delivery.send(
            "https://discord.com/api/webhooks/test", {"content": "paper"},
            opener=lambda request, timeout: (requests.append(request) or Response()))
        self.assertEqual(message_id, "123456789012345678")
        self.assertEqual(requests[0].get_header("User-agent"), "StatRally/0.1")

    def entry(self):
        start = datetime.now(timezone.utc) + timedelta(minutes=50)
        observed = start - timedelta(minutes=50)
        return {"schema_version": "nhl-kalshi-moneyline-paper-v1",
                "paper_trade": True, "orders_placed": 0, "stage": "entry",
                "fixture_id": "123", "market_ticker": "KXNHLGAME-26NOV16MTLNYR-MTL",
                "game_start_utc": start.isoformat(),
                "observed_utc": observed.isoformat(),
                "model_forecast_created_utc": (observed - timedelta(minutes=1)).isoformat(),
                "market_identity_verified": True, "snapshot_sha256": "abc",
                "fixture_source_id": "def", "orderbook_source": "Kalshi",
                "ask_dollars": "0.55", "model_probability": "0.65",
                "scheduled_paper_fee_dollars": "0.02", "post_fee_edge": "0.08",
                "effective_fee_verified": True, "fee_exceptions_verified": True,
                "account_fill_fee": None, "paper_fee_execution_assumption": "taker_crossing_ask",
                "signal": "BUY_YES"}

    def test_valid_prospective_entry(self):
        self.assertTrue(delivery.eligible(self.entry()))

    def test_no_bet_and_unverified_fee_rejected(self):
        for signal in ("NO_BET", "NO_BET_EFFECTIVE_FEE_UNCONFIRMED", None):
            row = self.entry()
            row["signal"] = signal
            with self.assertRaises(ValueError):
                delivery.eligible(row)
        row = self.entry()
        row["effective_fee_verified"] = False
        with self.assertRaises(ValueError):
            delivery.eligible(row)

    def test_reject_inconsistent_edge(self):
        row = self.entry()
        row["post_fee_edge"] = "0.10"
        with self.assertRaises(ValueError):
            delivery.eligible(row)

    def test_qualified_pick_card_label(self):
        calls = []
        def api(method, repo, path, data=None):
            if method == "GET":
                return []
            if method == "POST" and path == "/issues":
                return {"number": 99}
            return {"id": 42}
        def sender(webhook, payload):
            calls.append(payload)
            return "123456789"
        with patch.dict("os.environ", {"STATRALLY_NHL_PICKS_WEBHOOK":
                                      "https://discord.com/api/webhooks/test"}, clear=False):
            result = delivery.publish("picks", self.entry(), {}, call=api, sender=sender)
        self.assertEqual(result["state"], "CONFIRMED")
        self.assertIn("[PAPER TRADE]", calls[0]["embeds"][0]["description"])

    def test_reject_backdated_entry(self):
        row = self.entry()
        row["observed_utc"] = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        with self.assertRaises(ValueError):
            delivery.eligible(row)

    def test_reject_live_orders(self):
        row = self.entry()
        row["orders_placed"] = 1
        with self.assertRaises(ValueError):
            delivery.eligible(row)

    def test_ambiguous_send_is_not_retried(self):
        calls = []
        def api(method, repo, path, data=None):
            calls.append((method, path, data))
            if method == "POST" and path == "/issues":
                return {"number": 91}
            if method == "GET":
                return []
            return {"id": 42}
        with patch.dict("os.environ", {"STATRALLY_NHL_WATCHLIST_WEBHOOK":
                                      "https://discord.com/api/webhooks/test"}, clear=False):
            result = delivery.publish("watchlist", self.entry(), {},
                call=api, sender=lambda *args: (_ for _ in ()).throw(TimeoutError()))
        self.assertEqual(result["state"], "AMBIGUOUS_OR_FAILED")
        self.assertTrue(any("AMBIGUOUS_OR_FAILED" in str(x) for x in calls))


if __name__ == "__main__":
    unittest.main()
