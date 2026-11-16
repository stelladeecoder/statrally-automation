"""Offline regression tests for NHL paper ledger delivery safety."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import nhl_moneyline_ledger_delivery as delivery


class PaperDeliveryTests(unittest.TestCase):
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
                "ask_dollars": "0.55"}

    def test_valid_prospective_entry(self):
        self.assertTrue(delivery.eligible(self.entry()))

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
