import unittest
from datetime import datetime,timezone
from replace_nhl_watchlist_today import replace,ISSUE_TITLE
from send_nhl_watchlist_test import EXPECTED_CHANNEL_ID
from tests_fixture_nhl import dummy
NOW=datetime(2026,11,14,18,0,tzinfo=timezone.utc)
class ReplacementTests(unittest.TestCase):
    def test_replace_once_and_remove_original(self):
        records=[]
        def call(method,repo,path,data=None):
            if method=="GET":return records
            if method=="POST":
                x={"title":data["title"],"body":data["body"],"number":77,
                   "user":{"login":"github-actions[bot]"}}
                records.append(x)
                return x
            if method=="PATCH":return {"number":77}
            raise AssertionError((method,path))
        sent=[]
        deleted=[]
        with dummy():
            result=replace("owner/repo","https://discord.com/api/webhooks/1/x",
                now=NOW,call=call,sender=lambda hook,payload:sent.append(payload) or "123456789",
                verifier=lambda *_:{"verified":True,"channel_id":EXPECTED_CHANNEL_ID},
                old_checker=lambda *_:True,deleter=lambda *_:deleted.append(True))
            self.assertTrue(result["sent"])
            self.assertTrue(result["old_deleted"])
            self.assertEqual(len(deleted),1)
            self.assertEqual(len(sent),1)
            text=sent[0]["embeds"][0]["description"]
            self.assertNotIn("%",text)
            self.assertNotIn("EVEN ",text)
            self.assertNotIn("ODD ",text)
            self.assertEqual(text.count("• Away"),14)
            second=replace("owner/repo","https://discord.com/api/webhooks/1/x",
                now=NOW,call=call,sender=lambda *_:self.fail("Duplicate Discord send"),
                verifier=lambda *_:{"verified":True,"channel_id":EXPECTED_CHANNEL_ID},
                old_checker=lambda *_:True,deleter=lambda *_:self.fail("Duplicate delete"))
            self.assertFalse(second["sent"])
    def test_verify_wrong_channel_before_sending(self):
        with self.assertRaisesRegex(ValueError,"not verified"):
            replace("owner/repo","https://discord.com/api/webhooks/1/x",now=NOW,
              verifier=lambda *_:{"verified":True,"channel_id":"incorrect"})
    def test_date_guard(self):
        with self.assertRaisesRegex(ValueError,"restricted"):
            replace("owner/repo","https://discord.com/api/webhooks/1/x",
              now=datetime(2026,11,15,18,tzinfo=timezone.utc))
if __name__=="__main__":
    unittest.main()
