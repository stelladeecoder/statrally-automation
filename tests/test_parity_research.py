import unittest
from datetime import datetime,timezone,timedelta
from parity_research import parse_scoreboard,probability,build_report,backtest,LEAGUES
from parity_discord import render,publish

NOW=datetime(2026,11,14,8,0,tzinfo=timezone.utc)
def event(event_id,date="2026-11-14T20:00:00Z",status="STATUS_SCHEDULED",completed=False,
          home_score=None,away_score=None):
    h={"homeAway":"home","team":{"id":"19","displayName":"Home"}}
    a={"homeAway":"away","team":{"id":"16","displayName":"Away"}}
    if home_score is not None:h["score"]=str(home_score)
    if away_score is not None:a["score"]=str(away_score)
    return {"id":str(event_id),"date":date,"status":{"type":{"name":status,
        "completed":completed,"state":"post" if completed else "pre"}},
        "competitions":[{"competitors":[h,a]}]}

class ParityTests(unittest.TestCase):
    def test_soccer_even_zero_and_odd(self):
        payload={"events":[event(1,completed=True,status="STATUS_FULL_TIME",
                                  home_score=0,away_score=0),
                           event(2,completed=True,status="STATUS_FULL_TIME",
                                  home_score=2,away_score=1)]}
        rows=parse_scoreboard("soccer_epl",payload,"https://example.invalid")
        self.assertEqual([x["parity"] for x in rows],["EVEN","ODD"])
        self.assertEqual([x["score_total"] for x in rows],[0,3])
    def test_nhl_final_vs_soccer_status_and_odd_goal(self):
        payload={"events":[event(1,completed=True,status="STATUS_FINAL",
                                  home_score=4,away_score=3)]}
        self.assertEqual(parse_scoreboard("nhl",payload,"x")[0]["parity"],"ODD")
        self.assertEqual(parse_scoreboard("soccer_nwsl",payload,"x")[0]["status"],
                         "unsupported_final")
    def test_incomplete_and_conflicting_identity(self):
        self.assertEqual(parse_scoreboard("soccer_nwsl",{"events":[event(1)]},"x")[0]["status"],
                         "pregame")
        with self.assertRaises(ValueError):
            parse_scoreboard("soccer_nwsl",{"events":[event(1),event(1)]},"x")
        invalid=event(2)
        invalid["competitions"][0]["competitors"][1]["team"]["id"]="19"
        with self.assertRaisesRegex(ValueError,"team identities"):
            parse_scoreboard("soccer_nwsl",{"events":[invalid]},"x")
        with self.assertRaisesRegex(ValueError,"integer"):
            parse_scoreboard("nhl",{"events":[event(2,completed=True,status="STATUS_FINAL")]},"x")
    def test_pre_match_no_same_day_leakage(self):
        fixture={"id":"a","league":"soccer_epl","kickoff_utc":"2026-11-14T20:00:00Z"}
        old={"id":"b","league":"soccer_epl","status":"graded",
             "kickoff_utc":"2026-11-12T10:00:00Z","parity":"EVEN"}
        same=dict(old,id="c",kickoff_utc="2026-11-14T04:00:00Z",parity="ODD")
        result=probability(fixture,[old,same],NOW.isoformat(),minimum=1)
        self.assertEqual(result["sample_size"],1)
        self.assertFalse(result["qualified_bet"])
        self.assertAlmostEqual(result["p_even"]+result["p_odd"],1)
    def test_report_covers_men_women_and_nhl(self):
        keys=("soccer_epl","soccer_nwsl","nhl")
        def fetch(key,start,end):
            if (end-start).days<10:
                return parse_scoreboard(key,{"events":[event(777)]},"https://source.test")
            final_status="STATUS_FINAL" if key=="nhl" else "STATUS_FULL_TIME"
            return parse_scoreboard(key,{"events":[event(100, date="2026-11-03T10:00:00Z",
                    completed=True,status=final_status,home_score=0,away_score=0)]},"https://source.test")
        report=build_report(now=NOW,history_days=14,keys=keys,fetch=fetch)
        self.assertEqual(report["qualified_bets"],0)
        self.assertEqual(len(report["competitions"]),3)
        self.assertEqual([s["category"] for s in report["competitions"]],
                         ["men","women","men"])
        self.assertEqual(sum(x["pregame_count"] for x in report["competitions"]),3)
        message=render(report)["content"]
        self.assertIn("NWSL (Women)",message)
        self.assertIn("NHL",message)
        self.assertIn("Research beta only",message)
    def test_discord_safety(self):
        report={"schema_version":1,"market":"TOTAL_SCORE_PARITY",
            "status":"research_only","qualified_bets":1,"trades_placed":0,
            "models_promoted":False,"markets_verified":False,
            "sports":["soccer","hockey"],"competitions":[]}
        with self.assertRaises(ValueError):render(report)
    def test_empty_or_unknown_source_does_not_claim_fixture_coverage(self):
        with self.assertRaises(ValueError):
            parse_scoreboard("soccer_nwsl",{"broken":None},"source")
        with self.assertRaises(ValueError):
            build_report(now=NOW,keys=("wrong",))
if __name__=="__main__":
    unittest.main()
