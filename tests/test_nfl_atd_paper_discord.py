import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from nfl_atd_paper_discord import decisions, deliver, periods, run_picks, run_recaps, settle_rows

NOW = datetime(2026, 11, 27, 12, tzinfo=timezone.utc)
ENTRY = {"fixture_id":"2026w11-IND-HOU","player_id":"00-0000001",
         "market_ticker":"KXNFLANYTD-TEST","observed_utc":"2026-11-19T23:55:00Z",
         "kickoff_utc":"2026-11-20T01:15:00Z","sport":"nfl","market_type":"atd",
         "signal":"BUY_YES","paper_only":True,"orders_placed":0,
         "ask_dollars":"0.50","model_probability":"0.60",
         "scheduled_paper_fee_dollars":"0.02","post_fee_edge":"0.08",
         "model_sha256":"a"*64,"orderbook_sha256":"b"*64}


def decision_report(*records):
    return {"schema":"nfl-atd-paper-decisions-v1","paper_only":True,
            "orders_placed":0,"records":records}


class NflDiscordTest(unittest.TestCase):
    def test_picks_filter_missing_evidence_and_deduplicate(self):
        now = datetime(2026, 11, 20, 0, tzinfo=timezone.utc)
        records = [decision_report(ENTRY, ENTRY, {"signal":"NO_BET"}, {"reason":"skip"})]
        sent = []
        run_picks(decisions(records, now), now, publish=lambda *args:sent.append(args))
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][1], "STATRALLY_NFL_PICKS_WEBHOOK")
        self.assertIn("[PAPER TRADE]", sent[0][2])
        with self.assertRaises(ValueError):
            decisions([decision_report(dict(ENTRY, post_fee_edge="0.09"))], now)
        with self.assertRaises(KeyError):
            decisions([decision_report({k:v for k,v in ENTRY.items() if k != "orderbook_sha256"})], now)

    def test_closed_central_dates_revisit_seven_days(self):
        days = [end.isoformat() for kind, _, end in periods(NOW) if kind == "daily"]
        self.assertEqual((len(days), days[0], days[-1]), (7, "2026-11-20", "2026-11-26"))
        entries = decisions([decision_report(ENTRY)], NOW)
        outcome = {"schema":"nfl-atd-paper-settlement-v1","sport":"nfl","market_type":"atd",
                   "fixture_id":ENTRY["fixture_id"],"player_id":ENTRY["player_id"],
                   "ticker":ENTRY["market_ticker"],"paper_only":True,"orders_placed":0,
                   "settled_at_utc":"2026-11-21T05:30:00Z","settlement_result":"yes",
                   "entry_cost_dollars":"0.52","post_fee_paper_pnl_dollars":"0.48",
                   "closing_line_value_dollars":"0.01"}
        rows = settle_rows(entries, [{"paper_only":True,"orders_placed":0,"records":[outcome]}], NOW)
        sent = []
        run_recaps(rows, NOW, publish=lambda *args:sent.append(args))
        daily = next(row for row in sent if "Daily" in row[2])
        self.assertEqual(daily[1], "STATRALLY_NFL_RESULTS_WEBHOOK")
        self.assertIn("Settlement dates 2026-11-20", daily[3])
        self.assertIn("W–L 1–0", daily[3])
        self.assertIn("$0.48", daily[3])

    def test_reservation_prevents_duplicate_webhook_posts(self):
        issues, sent = [], []
        def call(method, repo, path, data=None):
            if method == "GET":
                return issues
            if path == "/issues":
                issues.append({"number":123, **data})
                return issues[-1]
            return {"id":456}
        hook = "https://discord.com/api/webhooks/test"
        def sender(url, payload):
            sent.append(url)
            return "123456789012345678"
        with patch.dict("os.environ", {"STATRALLY_NFL_RESULTS_WEBHOOK":hook}):
            for _ in range(2):
                deliver("test", "STATRALLY_NFL_RESULTS_WEBHOOK", "Title", "Body",
                        call=call, sender=sender)
        self.assertEqual(sent, [hook])
