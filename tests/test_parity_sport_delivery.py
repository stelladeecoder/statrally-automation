import unittest
from parity_sport_delivery import pages,send_sport,destinations,BLUE
from parity_research import LEAGUES
from parity_discord import RESERVATION
def comp(key,games):
    return {"league":key,"competition_name":LEAGUES[key][2],
            "category":LEAGUES[key][3],"historical_games":60,
            "pregame_count":len(games),"fixtures":games}
def game(i):
    return {"id":str(i),"home":"Home"+str(i),"away":"Away"+str(i),
            "kickoff_utc":"2026-11-14T22:00:00+00:00",
            "forecast":{"status":"research_prediction","p_even":.4,"p_odd":.6,"qualified_bet":False}}
def report():
    return {"schema_version":1,"market":"TOTAL_SCORE_PARITY",
            "status":"research_only","qualified_bets":0,"trades_placed":0,
            "models_promoted":False,"markets_verified":False,
            "day_central":"2026-11-14","competitions":[
              comp("soccer_nwsl",[game(1)]),comp("nhl",[game(i) for i in range(2,16)])]}
class SportDeliveryTests(unittest.TestCase):
    def test_sport_separation_and_full_nhl_slate(self):
        data=report()
        soccer=pages(data,"soccer")
        hockey=pages(data,"hockey")
        self.assertEqual(len(soccer),1)
        self.assertEqual(len(hockey),1)
        self.assertIn("NWSL (Women)",soccer[0]["embeds"][0]["description"])
        self.assertNotIn("NHL",soccer[0]["embeds"][0]["description"])
        text=hockey[0]["embeds"][0]["description"]
        for i in range(2,16):
            self.assertIn("Away"+str(i)+" @ Home"+str(i),text)
        self.assertNotIn("more nhl fixtures",text)
        self.assertEqual(hockey[0]["embeds"][0]["color"],BLUE)
        self.assertIn("WATCHLIST",hockey[0]["embeds"][0]["title"])
        for payload in soccer+hockey:
            self.assertNotIn("EVEN 40.0%",payload["embeds"][0]["description"])
            self.assertNotIn("ODD 60.0%",payload["embeds"][0]["description"])
            self.assertNotIn("%",payload["embeds"][0]["description"])
    def test_pagination_keeps_every_game(self):
        data=report()
        data["competitions"][1]=comp("nhl",[game(i) for i in range(200,340)])
        pageset=pages(data,"hockey")
        self.assertGreater(len(pageset),1)
        descriptions="\n".join(p["embeds"][0]["description"] for p in pageset)
        for i in range(200,340):
            self.assertIn("Away"+str(i)+" @ Home"+str(i),descriptions)
    def test_reject_unverified(self):
        data=report()
        data["competitions"][1]["fixtures"][0]["forecast"]["qualified_bet"]=True
        with self.assertRaises(ValueError):pages(data,"hockey")
    def test_nhl_never_falls_back_to_soccer_channel(self):
        routes=destinations({"STATRALLY_PARITY_DISCORD_WEBHOOK":"https://discord.com/api/webhooks/soccer"})
        self.assertEqual(routes["soccer"],"https://discord.com/api/webhooks/soccer")
        self.assertEqual(routes["hockey"],"")
    def test_nhl_dedicated_channel_and_identical_webhook_rejection(self):
        soccer="https://discord.com/api/webhooks/soccer"
        hockey="https://discord.com/api/webhooks/hockey"
        config={"STATRALLY_PARITY_DISCORD_WEBHOOK":soccer,
                "STATRALLY_NHL_WATCHLIST_WEBHOOK":hockey}
        self.assertEqual(destinations(config),{"soccer":soccer,"hockey":hockey})
        config["STATRALLY_NHL_WATCHLIST_WEBHOOK"]=soccer
        with self.assertRaisesRegex(ValueError,"cannot be identical"):
            destinations(config)
    def test_legacy_hockey_webhook_cannot_route_to_wrong_channel(self):
        old={"STATRALLY_PARITY_HOCKEY_WEBHOOK":"https://discord.com/api/webhooks/old-hockey"}
        self.assertEqual(destinations(old)["hockey"],"")
    def test_nhl_picks_results_secrets_do_not_contaminate_watchlist(self):
        routes=destinations({
            "STATRALLY_NHL_PICKS_WEBHOOK":"https://discord.com/api/webhooks/nhl-picks",
            "STATRALLY_NHL_RESULTS_WEBHOOK":"https://discord.com/api/webhooks/nhl-results",
        })
        self.assertEqual(routes["hockey"],"")
    def test_explicit_soccer_channel_takes_precedence(self):
        config={"STATRALLY_PARITY_SOCCER_WEBHOOK":"soccer-channel",
                "STATRALLY_PARITY_DISCORD_WEBHOOK":"old-channel",
                "STATRALLY_NHL_WATCHLIST_WEBHOOK":"hockey-channel"}
        self.assertEqual(destinations(config)["soccer"],"soccer-channel")
    def test_independent_delivery_and_duplicate_gate(self):
        data=report()
        records=[]
        def api(method,repo,path,body=None):
            if method=="GET":return records
            if method=="POST" and path=="/issues":
                rec={"title":body["title"],"body":body["body"],
                     "number":len(records)+10,"user":{"login":"github-actions[bot]"}}
                records.append(rec);return rec
            if method=="POST" and path.endswith("/comments"):
                return {"id":123}
            if method=="PATCH":return {"number":10}
            raise AssertionError((method,path))
        sent=[]
        def sender(url,payload):
            sent.append(payload)
            return str(len(sent))
        for sport in ("soccer","hockey"):
            result=send_sport(data,sport,"o/r","https://discord.com/api/webhooks/1/x",
                              call=api,sender=sender)
            self.assertEqual(result["status"],"confirmed" if sport=="soccer" else "retired_for_moneyline")
        self.assertEqual(len(sent),1)
        repeat=send_sport(data,"soccer","o/r","https://discord.com/api/webhooks/1/x",
                          call=api,sender=sender)
        self.assertEqual(repeat["status"],"previously_reserved_no_retry")
        self.assertEqual(len(sent),1)
if __name__=="__main__":
    unittest.main()
