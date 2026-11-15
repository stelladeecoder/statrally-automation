"""Private NHL snapshot health aggregation: no invented receipts or exposed secrets."""
import sys
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from nhl_moneyline_admin_health import aggregate, obtain, lines_for_day, PREFIX, TITLE

DAY="2026-11-15"
def rec(run,statuses):
    return {"paper_only":True,"orders_placed":0,
            "workflow":"nhl-moneyline-five-minute-paper-poller.yml",
            "run_id":str(run),"poll_status":"complete",
            "events":statuses}
def event(stage,status,team="KXNHLGAME-TEAM"):
    return {"fixture_id":"2026020326","contract":team,
            "stage":stage,"status":status}
class HealthTests(unittest.TestCase):
    def test_dedup_real_stage_successes_and_missed_receipts(self):
        report=aggregate([
            rec(1,[event("entry","low_liquidity_skip"),
                   event("entry","entry_hit","KXNHLGAME-OTHER")]),
            rec(2,[event("entry","entry_hit"),
                   event("entry","entry_duplicate","KXNHLGAME-OTHER")]),
            rec(3,[event("close","close_hit"),
                   event("close","close_missing_entry","KXNHLGAME-OTHER")])
        ])
        self.assertEqual(report["polls"],3)
        self.assertEqual(report["entry_hits"],2)
        self.assertEqual(report["entry_misses"],0)
        self.assertEqual(report["close_hits"],1)
        self.assertEqual(report["close_misses"],1)
        self.assertEqual(report["low_liquidity_skips"],1)

    def test_no_issue_is_unknown_not_zero(self):
        def fake(path,*,token):
            return []
        self.assertIsNone(obtain(DAY,token="masked",call=fake))
        self.assertIn("unknown",lines_for_day(DAY,token="masked",call=fake)[0])

    def test_missing_private_token_reported_without_token(self):
        self.assertIn("TOKEN MISSING",lines_for_day(DAY,token="")[0])

    def test_private_bot_comments_are_only_trusted_records(self):
        body=PREFIX+'{"day":"2026-11-15","paper_only":true,"orders_placed":0}'
        comment=PREFIX+__import__("json").dumps(rec(9,[event("entry","entry_hit")]))
        def fake(path,*,token):
            if path.startswith("/issues?"):
                return [{"number":14,"title":TITLE+DAY,
                    "user":{"login":"github-actions[bot]"},"body":body}]
            if "/comments" in path:
                return [{"user":{"login":"github-actions[bot]"},"body":comment},
                        {"user":{"login":"other"},"body":comment}]
            self.fail(path)
        value=obtain(DAY,token="masked",call=fake)
        self.assertEqual(len(value),1)
        self.assertIn("Entry snapshot contract hits/misses: 1/0",
                      lines_for_day(DAY,token="masked",call=fake))

    def test_duplicate_run_receipt_fails_closed(self):
        with self.assertRaises(ValueError):
            aggregate([rec(8,[]),rec(8,[])])

    def test_bad_secret_never_appears_in_admin_error(self):
        def fail(*args,**kwargs):
            raise RuntimeError("sensitive message maybe contains token")
        line=lines_for_day(DAY,token="secret-private-token",call=fail)[0]
        self.assertNotIn("secret-private-token",line)
        self.assertNotIn("sensitive",line)
        self.assertIn("HEALTH READ ERROR",line)

if __name__=="__main__":unittest.main()
