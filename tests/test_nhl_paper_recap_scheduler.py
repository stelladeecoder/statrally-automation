"""Verify recap delivery and Central settlement date accounting."""
import unittest
from unittest.mock import patch
from datetime import date, datetime, timezone
from decimal import Decimal
from nhl_paper_recap_scheduler import publish_recap, run, summarize


class CompleteSlateTests(unittest.TestCase):
    def test_synthetic_recap_formatter_and_mock_discord_receipt(self):
        sent=[]
        api_calls=[]
        def api(method, repo, path, data=None):
            api_calls.append((method,path,data))
            if method=="GET":
                return []
            if method=="POST" and path=="/issues":
                return {"number":193}
            return {"id":123}
        def sender(webhook,payload):
            sent.append((webhook,payload))
            return "123456789012345678"
        day = date(2026, 11, 16)
        data = summarize([("1", day, day, (False, Decimal("-0.20"),
                          Decimal("0.20"), Decimal("0.04")))], day, day, 2)
        with patch.dict("os.environ",{"STATRALLY_NHL_DAILY_RECAP_WEBHOOK":
                       "https://discord.com/api/webhooks/TEST_ONLY"},clear=False):
            result=publish_recap("daily","2026-11-16",data,call=api,sender=sender)
        self.assertEqual(result["status"],"CONFIRMED")
        self.assertEqual(len(sent),1)
        embed=sent[0][1]["embeds"][0]
        self.assertEqual(embed["title"], "StatRally · Daily Recap")
        self.assertIn("🏒 **NHL Moneyline** · 0W / 1L · **0.0%**",embed["description"])
        self.assertIn("**Soccer BTTS** · Inactive",embed["description"])
        self.assertIn("Post-fee PAPER P&L",embed["description"])
        self.assertIn("-$0.20",embed["description"])
        self.assertEqual(embed["color"], 3447003)
        self.assertIn("Monday, November 16 · Central Time",embed["description"])
        self.assertIn("**Combined** · 0W / 1L",embed["description"])
        self.assertNotIn("Even/Odd",str(embed))
        self.assertTrue(any("123456789012345678" in str(row) for row in api_calls))
        # Mock sender only: never calls a real Discord webhook or mutates production ledger.

    def test_scheduler_revisits_a_previous_settlement_date(self):
        day = date(2026, 11, 16)
        rows = [("1", day, day,
                 (True, Decimal("0.43"), Decimal("0.57"), Decimal("0.05")))]
        with patch("nhl_paper_recap_scheduler.qualified_trades", return_value=rows), \
             patch("nhl_paper_recap_scheduler.publish_recap") as publish:
            run(now=datetime(2026, 11, 19, 12, tzinfo=timezone.utc),
                schedule=lambda day: set(), source=dict)
        publish.assert_called_once()
        self.assertEqual(publish.call_args.args[:2], ("daily", "2026-11-16"))
        self.assertEqual(publish.call_args.args[2]["wins"], 1)

    def test_quiet_slate(self):
        day = date(2026, 11, 16)
        recap = summarize([], day, day, 2)
        self.assertEqual(recap["trades_placed"], 0)
        self.assertEqual(recap["settled_contracts"], 0)
        self.assertEqual(recap["post_fee_paper_pnl_dollars"], "0.00")

    def test_settlement_crosses_central_midnight(self):
        entry = date(2026, 11, 16)
        settlement = date(2026, 11, 17)
        rows = [("1", entry, settlement,
                 (True, Decimal("0.43"), Decimal("0.57"), Decimal("0.05")))]
        before = summarize(rows, entry, entry, 8)
        after = summarize(rows, settlement, settlement, 0)
        self.assertEqual(before["pending"], 1)
        self.assertEqual(before["settled_contracts"], 0)
        self.assertEqual(after["pending"], 0)
        self.assertEqual(after["wins"], 1)
        self.assertEqual(after["settlement_dates"], ["2026-11-17"])
        self.assertEqual(after["post_fee_paper_pnl_dollars"], "0.43")


if __name__=="__main__":
    unittest.main()
