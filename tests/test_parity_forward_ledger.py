import unittest
from datetime import datetime,timedelta,timezone
from parity_forward_ledger import (archive,verified_result,grade_repo,PREFIX,GRADE,TITLE)
from parity_research import LEAGUES
NOW=datetime(2026,11,14,15,0,tzinfo=timezone.utc)

def fixture(league="soccer_epl",game="espn:soccer:eng.1:1",kick="2026-11-14T19:00:00+00:00"):
    return {"id":game,"league":league,"sport":LEAGUES[league][0],
            "category":LEAGUES[league][3],"settlement_basis":LEAGUES[league][4],
            "home":"Home","away":"Away","home_team_id":"19","away_team_id":"16",
            "kickoff_utc":kick,
            "forecast":{"status":"research_prediction","p_even":.55,"p_odd":.45,
                "qualified_bet":False,"as_of_utc":NOW.isoformat()}}
def snapshot():
    from parity_research import LEAGUES
    def competition(key,fixt):
        return {"league":key,"category":LEAGUES[key][3],
                "competition_name":LEAGUES[key][2],
                "settlement_basis":LEAGUES[key][4],
                "pregame_count":len(fixt),"historical_games":32,"fixtures":fixt}
    f1=fixture()
    f2=fixture("nhl","espn:hockey:nhl:2","2026-11-14T22:00:00+00:00")
    return {"schema_version":1,"market":"TOTAL_SCORE_PARITY",
        "status":"research_only","markets_verified":False,"prices_verified":False,
        "models_promoted":False,"qualified_bets":0,"trades_placed":0,
        "day_central":"2026-11-14","generated_at":NOW.isoformat(),
        "sports":["soccer","hockey"],"competitions":[
            competition("soccer_epl",[f1]),competition("nhl",[f2])]}

class FakeAPI:
    def __init__(self):
        self.saved=[];self.comments={};self.next=100
    def call(self,method,repo,path,data=None):
        if method=="GET" and path.startswith("/issues?"):
            return list(self.saved)
        if method=="POST" and path=="/issues":
            i={"title":data["title"],"body":data["body"],"number":self.next,
               "user":{"login":"github-actions[bot]"}}
            self.next+=1;self.saved.append(i);return i
        if path.startswith("/issues/") and path.endswith("/comments?per_page=100&page=1"):
            no=int(path.split("/")[2])
            return self.comments.get(no,[])
        if method=="POST" and path.endswith("/comments"):
            no=int(path.split("/")[2])
            row={"id":200+len(self.comments.get(no,[])),
                "body":data["body"],"user":{"login":"github-actions[bot]"}}
            self.comments.setdefault(no,[]).append(row);return row
        raise AssertionError((method,path))

class LedgerTests(unittest.TestCase):
    def test_freeze_once_and_keep_original_probabilities(self):
        api=FakeAPI();data=snapshot()
        result=archive(data,"o/r",call=api.call)
        self.assertEqual(result["status"],"frozen")
        self.assertEqual(len(api.saved),1)
        self.assertTrue(api.saved[0]["body"].startswith(PREFIX))
        self.assertEqual(archive(data,"o/r",call=api.call)["status"],"already_frozen")
        data["competitions"][0]["fixtures"][0]["forecast"]["p_even"]=.6
        data["competitions"][0]["fixtures"][0]["forecast"]["p_odd"]=.4
        self.assertEqual(archive(data,"o/r",call=api.call)["status"],"already_frozen")
        self.assertEqual(len(api.saved),1)
    def test_invalid_future_or_mismatched_probability_rejected(self):
        from parity_forward_ledger import check_report
        data=snapshot()
        data["competitions"][0]["fixtures"][0]["forecast"]["p_even"]=.8
        with self.assertRaisesRegex(ValueError,"mass"):check_report(data)
        data=snapshot()
        data["competitions"][0]["fixtures"][0]["kickoff_utc"]=(NOW-timedelta(hours=1)).isoformat()
        with self.assertRaisesRegex(ValueError,"post-kickoff"):check_report(data)
    def test_verified_even_odd_and_pending_not_false_loss(self):
        row=fixture(kick="2026-11-13T20:00:00Z")
        response={**row,"status":"graded","parity":"EVEN","score_total":4,
                  "source":"https://site.api.espn.com/test"}
        actual=verified_result(row,now=NOW,fetch=lambda *a:[response])
        self.assertEqual(actual["actual"],"EVEN")
        self.assertEqual(actual["total"],4)
        self.assertEqual(verified_result(row,now=NOW,fetch=lambda *a:[])["status"],"unconfirmed")
        self.assertEqual(verified_result(fixture(),now=NOW)["status"],"pending")
        invalid=dict(response,away_team_id="999")
        with self.assertRaisesRegex(ValueError,"identity"):
            verified_result(row,now=NOW,fetch=lambda *a:[invalid])
    def test_grade_once_without_postkickoff_prediction(self):
        api=FakeAPI();data=snapshot()
        for c in data["competitions"]:
            for f in c["fixtures"]:
                f["kickoff_utc"]="2026-11-14T16:00:00+00:00"
        archive(data,"o/r",call=api.call)
        final=NOW+timedelta(days=1)
        def fetched(key,day,end):
            for c in data["competitions"]:
                if c["league"]!=key:continue
                f=c["fixtures"][0]
                return [{**f,"status":"graded","parity":"EVEN",
                         "score_total":2,"source":"https://site.api.espn.com/test"}]
            return []
        result=grade_repo("o/r",now=final,call=api.call,fetch=fetched)
        self.assertEqual(result["counts"]["newly_graded"],2)
        self.assertEqual(result["performance_by_league"]["nhl"]["n"],1)
        after=grade_repo("o/r",now=final,call=api.call,fetch=lambda *a:[])
        self.assertEqual(after["counts"]["previously_graded"],2)
        self.assertEqual(sum(len(v) for v in api.comments.values()),2)
    def test_missing_or_untrusted_archive_rejected(self):
        api=FakeAPI();archive(snapshot(),"o/r",call=api.call)
        api.saved[0]["user"]["login"]="stranger"
        with self.assertRaisesRegex(ValueError,"Untrusted"):
            grade_repo("o/r",now=NOW,call=api.call,fetch=lambda *a:[])

if __name__=="__main__":
    unittest.main()
