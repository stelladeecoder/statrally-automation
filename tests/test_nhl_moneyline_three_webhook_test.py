import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from nhl_moneyline_three_webhook_test import check

ENV={
    "STATRALLY_NHL_WATCHLIST_WEBHOOK":"https://discord.com/api/webhooks/a/first",
    "STATRALLY_NHL_PICKS_WEBHOOK":"https://discord.com/api/webhooks/b/second",
    "STATRALLY_NHL_RESULTS_WEBHOOK":"https://discord.com/api/webhooks/c/third",
}
class TestNHLWebhookConnectivity(unittest.TestCase):
    def test_three_independent_receipts(self):
        count=[]
        def verify(url):
            return str(100+len(count)+list(ENV.values()).index(url))
        def sender(url,payload):
            count.append(payload["content"])
            self.assertIn("[TEST / PAPER]",payload["content"])
            self.assertIn("NOT active",payload["content"])
            return str(len(count)+200)
        result=check(ENV,verifier=verify,sender=sender)
        self.assertEqual(result["message_count"],3)
        self.assertEqual(result["orders_placed"],0)

    def test_duplicate_secret_blocks_all_sends(self):
        env=dict(ENV)
        env["STATRALLY_NHL_PICKS_WEBHOOK"]=env["STATRALLY_NHL_WATCHLIST_WEBHOOK"]
        with self.assertRaises(ValueError):
            check(env,verifier=lambda _: "123",sender=lambda *_:self.fail("sent"))

    def test_missing_secret_blocks_all_sends(self):
        env=dict(ENV)
        del env["STATRALLY_NHL_RESULTS_WEBHOOK"]
        with self.assertRaises(ValueError):
            check(env,verifier=lambda _: "123",sender=lambda *_:self.fail("sent"))

if __name__=="__main__":
    unittest.main()
