import unittest
from datetime import datetime,timezone
from parity_discord_cards import picks_preview,result_card,BLUE,GREEN,RED
from parity_sport_delivery import pages
from test_parity_sport_delivery import report,comp,game
NOW=datetime(2026,11,14,16,0,tzinfo=timezone.utc)

def candidate():
    return {"id":"espn:hockey:nhl:12345","sport":"hockey","league":"nhl",
        "away":"Away Team","home":"Home Team",
        "kickoff_utc":"2026-11-14T23:00:00+00:00",
        "price_as_of_utc":"2026-11-14T15:59:00+00:00",
        "model_promoted":True,"model_calibrated":True,
        "market_verified":True,"qualified_bet":True,
        "market_id":"verified-contract-1","settlement_verified":True,
        "selection":"EVEN","p_even":.55,"p_odd":.45,
        "market_odds_decimal":2.03}
class CardsTests(unittest.TestCase):
    def test_watchlist_new_layout_total_and_no_probabilities(self):
        data=report()
        data["competitions"].append(comp("soccer_epl",[]))
        soccer=pages(data,"soccer")
        self.assertEqual(len(soccer),1)
        embed=soccer[0]["embeds"][0]
        self.assertIn("1 UPCOMING GAMES",embed["description"])
        self.assertIn("NWSL (Women)",embed["description"])
        self.assertNotIn("Premier League",embed["description"])
        self.assertEqual(embed["fields"][0]["value"],"2026-11-14")
        self.assertEqual(embed["fields"][1]["value"],"2")
        self.assertNotIn("%",embed["description"])
        self.assertIn("WATCHLIST",embed["title"])
    def test_verified_picks_card_is_blue_with_model_and_market(self):
        x=picks_preview("hockey","2026-11-14",[candidate()],now=NOW)
        self.assertEqual(x["embeds"][0]["color"],BLUE)
        self.assertIn("55.0%",x["embeds"][0]["description"])
        self.assertIn("2.03 decimal",x["embeds"][0]["description"])
        self.assertEqual(x["allowed_mentions"],{"parse":[]})
    def test_cannot_post_unqualified_model_or_missing_odds(self):
        x=candidate();x["model_calibrated"]=False
        with self.assertRaisesRegex(ValueError,"Unapproved"):
            picks_preview("hockey","2026-11-14",[x],now=NOW)
        x=candidate();x["market_odds_decimal"]=None
        with self.assertRaisesRegex(ValueError,"market odds"):
            picks_preview("hockey","2026-11-14",[x],now=NOW)
        x=candidate();x["kickoff_utc"]="2026-11-14T15:30:00+00:00"
        with self.assertRaisesRegex(ValueError,"Post-kickoff"):
            picks_preview("hockey","2026-11-14",[x],now=NOW)
    def test_results_show_correctness_not_wager_payout(self):
        r={"id":"espn:hockey:nhl:12345","sport":"hockey","league":"nhl",
           "home":"Home Team","away":"Away Team","grade_status":"graded",
           "final_verified":True,"original_forecast_saved":True,"total":5,
           "actual":"ODD","predicted":"ODD"}
        yes=result_card(r)["embeds"][0]
        self.assertEqual(yes["color"],GREEN)
        self.assertIn("Correct forecast",yes["description"])
        r["predicted"]="EVEN"
        no=result_card(r)["embeds"][0]
        self.assertEqual(no["color"],RED)
        self.assertIn("Incorrect forecast",no["description"])
        self.assertNotIn("profit",no["description"].lower())
    def test_unverified_result_is_blocked(self):
        r={"id":"espn:soccer:eng.1:222","sport":"soccer","league":"soccer_epl",
           "home":"Arsenal","away":"Chelsea","grade_status":"pending",
           "final_verified":False,"original_forecast_saved":True,"total":3,
           "actual":"ODD","predicted":"ODD"}
        with self.assertRaisesRegex(ValueError,"Unverified"):
            result_card(r)
if __name__=="__main__":
    unittest.main()
