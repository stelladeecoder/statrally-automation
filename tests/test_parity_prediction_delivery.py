import unittest
from datetime import datetime,timezone
from parity_prediction_delivery import cards,publish_one,BLUE
NOW=datetime(2026,11,14,17,10,tzinfo=timezone.utc)
def report():
    return {"schema_version":1,"status":"research_only_not_promoted",
            "source_repository":"stelladeecoder/statrally-even-odd-models",
            "source_run_id":123,"input_day":"2026-11-14",
            "exported_at":"2026-11-14T17:00:00+00:00",
            "calibrated":False,"qualified_bets":0,"production_enabled":False,
            "forecasts":[
              {"id":"espn:soccer:bra.1:555","league":"soccer_brasileirao",
               "sport":"soccer","status":"research_forecast_not_promoted",
               "home":"Mirassol","away":"Atlético-MG",
               "calibration_evaluated":True,"p_even":.48,"p_odd":.52,
               "prediction":"ODD","issued_at":"2026-11-14T17:00:00+00:00",
               "kickoff_utc":"2026-11-14T22:00:00+00:00"},
              {"id":"espn:hockey:nhl:999","league":"nhl","sport":"hockey",
               "status":"research_forecast_not_promoted","home":"Blues","away":"Wild",
               "calibration_evaluated":True,"p_even":.502,"p_odd":.498,
               "prediction":"EVEN","issued_at":"2026-11-14T17:00:00+00:00",
               "kickoff_utc":"2026-11-14T23:00:00+00:00"}]}
class EvenOddPicksTests(unittest.TestCase):
    def test_two_sports_show_selection_without_market_odds(self):
        for sport,pick in (("soccer","ODD"),("hockey","EVEN")):
            group=cards(report(),sport,now=NOW)
            self.assertEqual(len(group),1)
            embed=group[0]["embeds"][0]
            self.assertEqual(embed["color"],BLUE)
            self.assertIn(pick,embed["description"])
            self.assertNotIn("decimal",embed["description"])
            self.assertNotIn("market odds",embed["description"].lower())
            self.assertIn("Experimental",embed["fields"][1]["value"])
    def test_probability_category_uses_unrounded_selected_side(self):
        for sport, side, probability, expected in (
            ("soccer", "ODD", .70, True),
            ("hockey", "EVEN", .71, True),
            ("soccer", "ODD", .6999, False),
        ):
            with self.subTest(sport=sport, side=side, probability=probability):
                snap=report()
                row=next(row for row in snap["forecasts"] if row["sport"]==sport)
                row["p_"+side.lower()]=probability
                description=cards(snap,sport,now=NOW)[0]["embeds"][0]["description"]
                self.assertEqual(f"⭐ **{side}**" in description,expected)
                self.assertEqual("⭐ 🟨 **VERY HIGH MODEL PROBABILITY · 70%+**" in description,expected)
                if not expected:
                    self.assertIn("<70%",description)

    def test_tomorrow_not_mislabeled_as_todays_picks(self):
        snap=report()
        snap["forecasts"][1]["kickoff_utc"]="2026-11-16T01:00:00+00:00"
        self.assertEqual(cards(snap,"hockey",now=NOW),[])
    def test_postkickoff_does_not_backdate(self):
        snap=report()
        snap["forecasts"][1]["kickoff_utc"]="2026-11-14T16:00:00+00:00"
        self.assertEqual(cards(snap,"hockey",now=NOW),[])
    def test_unverified_or_stale_rejected(self):
        snap=report()
        snap["qualified_bets"]=1
        with self.assertRaisesRegex(ValueError,"Unverified"):
            cards(snap,"soccer",now=NOW)
        snap=report()
        snap["forecasts"][0]["calibration_evaluated"]=False
        with self.assertRaisesRegex(ValueError,"Unverified"):
            cards(snap,"soccer",now=NOW)
    def test_delivery_once_and_confirm_receipt(self):
        seen=[]
        posts=[]
        def call(method,repo,path,data=None):
            if method=="GET":return seen
            if method=="POST" and path=="/issues":
                issue={"number":777,"title":data["title"],"body":data["body"],
                       "user":{"login":"github-actions[bot]"}}
                seen.append(issue)
                return issue
            if method=="POST" and path.endswith("/comments"):
                return {"id":22}
            if method=="PATCH":return {"number":777}
            raise AssertionError((method,path))
        def sender(webhook,payload):
            posts.append(payload)
            return "123456"
        a=publish_one(report(),"hockey","owner/repo","https://discord.com/api/webhooks/1/x",
                      now=NOW,call=call,sender=sender)
        self.assertEqual(a["delivered"],1)
        b=publish_one(report(),"hockey","owner/repo","https://discord.com/api/webhooks/1/x",
                      now=NOW,call=call,sender=sender)
        self.assertEqual(b["status"],"previously_reserved_no_duplicate")
        self.assertEqual(len(posts),1)
    def test_missing_channel_not_falsely_success(self):
        r=publish_one(report(),"soccer","o/r","",now=NOW)
        self.assertEqual(r["status"],"dedicated_webhook_missing")
if __name__=="__main__":unittest.main()
