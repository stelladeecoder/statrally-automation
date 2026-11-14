import unittest
from io import BytesIO
from verify_nhl_watchlist_webhook import verify

class Reply:
    status=200
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n=-1):return b'{"id":"99887766","channel_id":"11223344","name":"NHL Bot"}'
class WebhookTests(unittest.TestCase):
    def test_missing(self):
        self.assertEqual(verify("","")["status"],"missing")
    def test_valid_read_only(self):
        calls=[]
        def opener(request,timeout):
            calls.append((request.get_method(),request.full_url,timeout))
            return Reply()
        result=verify("https://discord.com/api/webhooks/99887766/secret","https://discord.com/api/webhooks/other/secret",opener=opener)
        self.assertTrue(result["verified"])
        self.assertFalse(result["message_sent"])
        self.assertEqual(result["channel_id"],"11223344")
        self.assertEqual(calls[0][0],"GET")
    def test_reject_shared_webhook(self):
        link="https://discord.com/api/webhooks/99887766/secret"
        with self.assertRaisesRegex(ValueError,"identical"):
            verify(link,link)
    def test_reject_wrong_host(self):
        with self.assertRaisesRegex(ValueError,"origin"):
            verify("https://evil.example/api/webhooks/a/b","")
    def test_reject_unconfirmed_response(self):
        class NoChannel(Reply):
            def read(self,n=-1):return b'{"id":"99887766"}'
        with self.assertRaisesRegex(ValueError,"channel identity"):
            verify("https://discord.com/api/webhooks/99887766/secret","",opener=lambda *_args,**_kw:NoChannel())
if __name__=="__main__":
    unittest.main()
