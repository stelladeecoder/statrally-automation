"""Official slate completeness: no off-day or partial-slate publication."""
import unittest
from datetime import date
from decimal import Decimal
from nhl_paper_recap_scheduler import completed


def contract(game, ticker, pnl):
    common={"fixture_id":game,"market_ticker":ticker}
    return {"watchlist":{**common,"fixture_only":True,"market_identity_verified":True},
            "entry":common,"close":common,
            "settlement":{**common,"settlement_verified":True,"paper_only":True,
                          "orders_placed":0,"account_fill_fee":None,
                          "scheduled_paper_fee_dollars":"0.02",
                          "post_fee_paper_pnl_dollars":pnl}}


class CompleteSlateTests(unittest.TestCase):
    def test_off_day_no_recap(self):
        self.assertIsNone(completed(date(2026,11,16),schedule=lambda d:set(),
                                    source=lambda:{}))
    def test_missing_game_no_recap(self):
        d=date(2026,11,16)
        rows={(d,"1"):[contract("1","KXNHLGAME-ONE-A","0.30"),
                       contract("1","KXNHLGAME-ONE-B","-0.40")]}
        self.assertIsNone(completed(d,schedule=lambda day:{"1","2"},source=lambda:rows))
    def test_all_games_complete(self):
        d=date(2026,11,16)
        rows={(d,str(i)):[contract(str(i),f"KXNHLGAME-{i}-A","0.30"),
                          contract(str(i),f"KXNHLGAME-{i}-B","-0.40")]
              for i in (1,2)}
        result=completed(d,schedule=lambda day:{"1","2"},source=lambda:rows)
        self.assertEqual(result["settled_slate_games"],2)
        self.assertEqual(result["settled_contracts"],4)
        self.assertEqual(Decimal(result["post_fee_paper_pnl_dollars"]),Decimal("-0.20"))


if __name__=="__main__":
    unittest.main()
