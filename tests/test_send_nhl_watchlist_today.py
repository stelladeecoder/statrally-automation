import json
import unittest
from datetime import datetime,timezone
from send_nhl_watchlist_today import (
    send_today,build_frozen_nhl_report,DELIVERY_TITLE,DAY)
from send_nhl_watchlist_test import EXPECTED_CHANNEL_ID
from parity_forward_ledger import PREFIX, TITLE
NOW=datetime(2026,11,14,16,18,tzinfo=timezone.utc)

def fixture(n):
    return {"id":f"espn:hockey:nhl:{n}","league":"nhl","sport":"hockey","category":"men",
      "settlement_basis":"full_game_including_shootout_score",
      "home":f"Home {n}","away":f"Away {n}",
      "home_team_id":str(n+100),"away_team_id":str(n+200),
      "kickoff_utc":"2026-11-14T20:00:00+00:00",
      "forecast":{"status":"research_prediction","p_even":0.314815,"p_odd":0.685185,
                  "qualified_bet":False,"as_of_utc":"2026-11-14T15:29:47+00:00"}}

def source():
    record={"schema_version":1,"status":"unpromoted_forward_research","day_central":DAY,
            "generated_at":"2026-11-14T15:29:47+00:00",
            "qualified_bets":0,"trades_placed":0,
            "fixtures":[fixture(n) for n in range(14)]}
    return {"number":118,"title":TITLE+DAY,"body":PREFIX+json.dumps(record),
            "user":{"login":"github-actions[bot]"}}

class SameDayNHL(unittest.TestCase):
    def test_only_original_14_hockey_records(self):
        def call(method,repo,path,data=None):
            if path.startswith("/issues?"):return [source()]
            raise AssertionError(path)
        report=build_frozen_nhl_report("owner/repo",call=call)
        self.assertEqual(report["competitions"][0]["pregame_count"],14)
        self.assertEqual(report["competitions"][0]["fixtures"][0]["forecast"]["p_odd"],0.685185)
    def test_send_exactly_once_to_verified_channel(self):
        state=[source()];sends=[]
        def call(method,repo,path,data=None):
            if method=="GET":return state
            if method=="POST":
                issue={"number":119,"title":data["title"],"body":data["body"],
                       "user":{"login":"github-actions[bot]"}}
                state.append(issue)
                return issue
            if method=="PATCH":return {"number":119}
            raise AssertionError((method,path))
        def sender(url,payload):
            sends.append(payload)
            self.assertIn("#nhl-watchlist",payload["embeds"][0]["title"])
            self.assertEqual(payload["allowed_mentions"],{"parse":[]})
            for n in range(14):
                self.assertIn(f"Away {n} @ Home {n}",payload["embeds"][0]["description"])
            return "567890"
        verifier=lambda *_args:{"verified":True,"channel_id":EXPECTED_CHANNEL_ID}
        first=send_today("owner/repo","https://discord.com/api/webhooks/10/secret",
                 now=NOW,call=call,sender=sender,verifier=verifier)
        self.assertEqual(first["message_id"],"567890")
        self.assertEqual(first["games"],14)
        second=send_today("owner/repo","https://discord.com/api/webhooks/10/secret",
                 now=NOW,call=call,sender=sender,verifier=verifier)
        self.assertFalse(second["sent"])
        self.assertEqual(len(sends),1)
    def test_missing_or_wrong_destination_rejected(self):
        with self.assertRaisesRegex(ValueError,"not configured"):
            send_today("owner/repo","",now=NOW)
        with self.assertRaisesRegex(ValueError,"not verified"):
            send_today("owner/repo","https://discord.com/api/webhooks/10/secret",
                  now=NOW,verifier=lambda *_args:{"verified":True,"channel_id":"123"})
        with self.assertRaisesRegex(ValueError,"restricted"):
            send_today("owner/repo","x",now=datetime(2026,11,15,18,tzinfo=timezone.utc))
if __name__=="__main__":
    unittest.main()
