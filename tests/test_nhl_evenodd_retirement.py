"""NHL Even/Odd delivery is retired while soccer remains operational."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from parity_sport_delivery import send_sport
from parity_prediction_delivery import publish_one
import parity_individual_results as results

class TestNHLEvenOddRetirement(unittest.TestCase):
    def test_hockey_watchlist_refuses_send(self):
        def fail(*args,**kwargs):
            raise AssertionError("Retired NHL watchlist must never call Discord/GitHub")
        output=send_sport({},"hockey","owner/repo","https://unused",
                          call=fail,sender=fail)
        self.assertEqual(output["status"],"retired_for_moneyline")
        self.assertEqual(output["delivered"],0)

    def test_hockey_picks_refuses_send(self):
        def fail(*args,**kwargs):
            raise AssertionError("Retired NHL EvenOdd picks must never call Discord/GitHub")
        output=publish_one({},"hockey","owner/repo","https://unused",
                           call=fail,sender=fail)
        self.assertEqual(output["status"],"retired_for_moneyline")
        self.assertEqual(output["delivered"],0)

    def test_hockey_results_not_sent_but_soccer_remains_routable(self):
        row={"sport":"hockey","outcome":{"actual":"EVEN"},
             "forecast":{"id":"dummy"}}
        with patch.dict(os.environ,{"GITHUB_REPOSITORY":"owner/repo",
                                   "SOCCER_RESULTS_HOOK":"https://example.org/soccer",
                                   "NHL_RESULTS_HOOK":"https://example.org/nhl"}), \
             patch.object(results,"history",return_value=[]), \
             patch.object(results,"collect",return_value=[row]), \
             patch.object(results,"deliver",side_effect=AssertionError("NHL results sent")), \
             patch.object(sys,"argv",["parity_individual_results.py"]):
            results.main()

if __name__=="__main__":unittest.main()
