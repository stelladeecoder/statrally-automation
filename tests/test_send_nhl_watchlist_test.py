import unittest
from send_nhl_watchlist_test import send_test,EXPECTED_CHANNEL_ID

class SendNhlWatchlistTest(unittest.TestCase):
    def test_send_once_and_preserve_receipt(self):
        calls=[]
        def call(method,repo,path,data=None):
            calls.append((method,path,data))
            if method=="GET":return []
            if method=="POST":return {"number":13}
            if method=="PATCH":return {"number":13}
            self.fail(method)
        def sender(hook,payload):
            self.assertIn("TEST ONLY",payload["content"])
            self.assertEqual(payload["allowed_mentions"],{"parse":[]})
            self.assertIn("webhooks",hook)
            return "123456789"
        verifier=lambda *_args:{"verified":True,"channel_id":EXPECTED_CHANNEL_ID}
        result=send_test("https://discord.com/api/webhooks/123/x","owner/repo",
                         call=call,sender=sender,verifier=verifier)
        self.assertTrue(result["sent"])
        self.assertEqual(result["message_id"],"123456789")
        self.assertEqual([x[0] for x in calls],["GET","POST","PATCH"])
    def test_no_duplicate_message(self):
        def call(method,repo,path,data=None):
            return [{"title":"StatRally NHL watchlist webhook test | 2026-11-14",
                 "user":{"login":"github-actions[bot]"},
                 "body":"statrally-parity-beta-delivery-v1:{}"}]
        def sender(*args):self.fail("Duplicate test should not send")
        result=send_test("https://discord.com/api/webhooks/123/x","o/r",call=call,
                    sender=sender,verifier=lambda *_args:{"verified":True,
                                              "channel_id":EXPECTED_CHANNEL_ID})
        self.assertFalse(result["sent"])
    def test_wrong_channel_and_missing_webhook(self):
        with self.assertRaisesRegex(ValueError,"missing"):
            send_test("","o/r")
        with self.assertRaisesRegex(ValueError,"changed"):
            send_test("https://discord.com/api/webhooks/123/x","o/r",
                      verifier=lambda *_args:{"verified":True,"channel_id":"999"})
if __name__=="__main__":
    unittest.main()
