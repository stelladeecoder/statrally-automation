import json
import unittest
from datetime import datetime,timezone
from parity_public_snapshot import public_snapshot
from parity_forward_ledger import PREFIX,GRADE,TITLE
from parity_research import LEAGUES

class PublicProjectionTests(unittest.TestCase):
    def test_read_only_sanitized_projection_and_metrics(self):
        issue={"number":7,"title":TITLE+"2026-11-14","user":{"login":"github-actions[bot]"}}
        record={"schema_version":1,"status":"unpromoted_forward_research",
                "day_central":"2026-11-14","generated_at":"2026-11-14T11:00:00+00:00",
                "qualified_bets":0,"trades_placed":0,
                "fixtures":[{"id":"espn:soccer:eng.1:123","sport":"soccer",
                   "league":"soccer_epl","category":"men",
                   "home":"Home","away":"Away","home_team_id":"19","away_team_id":"16",
                   "kickoff_utc":"2026-11-14T19:00:00+00:00",
                   "settlement_basis":"90_minutes",
                   "forecast":{"status":"research_prediction","qualified_bet":False,
                       "p_even":.6,"p_odd":.4}}]}
        issue["body"]=PREFIX+json.dumps(record)
        grade={"id":"espn:soccer:eng.1:123","status":"graded",
               "actual":"EVEN","total":2,"source":"https://site.api.espn.com/final"}
        comment={"body":GRADE+json.dumps(grade),"user":{"login":"github-actions[bot]"}}
        def call(method,repo,path,data=None):
            if "/comments?" in path:return [comment]
            return [issue]
        result=public_snapshot("x/y",now=datetime(2026,11,15,tzinfo=timezone.utc),call=call)
        self.assertEqual(result["records"][0]["actual"],"EVEN")
        self.assertEqual(result["performance_by_league"][0]["graded"],1)
        self.assertEqual(result["performance_by_league"][0]["accuracy"],1)
        self.assertEqual(result["qualified_bets"],0)
        self.assertNotIn("home_team_id",result["records"][0])
        self.assertNotIn("source",result["records"][0])
        self.assertFalse(result["markets_verified"])
    def test_parity_proof_inconsistency_rejected(self):
        issue={"number":7,"title":TITLE+"2026-11-14",
          "user":{"login":"github-actions[bot]"},"body":PREFIX+json.dumps({
           "schema_version":1,"status":"unpromoted_forward_research",
           "day_central":"2026-11-14","generated_at":"2026-11-14T11:00:00+00:00",
           "qualified_bets":0,"trades_placed":0,"fixtures":[]})}
        comment={"body":GRADE+json.dumps({"id":"1","status":"graded",
            "actual":"EVEN","total":3}),"user":{"login":"github-actions[bot]"}}
        def call(method,repo,path,data=None):
            if "/comments?" in path:return [comment]
            return [issue]
        with self.assertRaisesRegex(ValueError,"Invalid historical parity proof"):
            public_snapshot("x/y",call=call)

if __name__=="__main__":
    unittest.main()
