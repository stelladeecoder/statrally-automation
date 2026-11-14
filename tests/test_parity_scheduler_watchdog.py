import unittest
from datetime import datetime,timezone
from parity_scheduler_watchdog import inspect,START
from parity_sport_delivery import PREFIX

RUN={"event":"schedule","head_branch":"main",
     "created_at":"2026-11-15T09:16:00Z",
     "conclusion":"success","status":"completed"}
NOW=datetime(2026,11,15,18,0,tzinfo=timezone.utc)
def receipt(sport="soccer"):
    import json
    return {"title":"StatRally parity "+sport+" | 2026-11-15",
            "user":{"login":"github-actions[bot]"},
            "body":PREFIX+json.dumps({"status":"confirmed","pages":1,
                                     "message_ids":["12345678"]})}

class WatchdogTests(unittest.TestCase):
    def test_predeployment_and_early_central_day(self):
        self.assertEqual(inspect(datetime(2026,11,14,18,tzinfo=timezone.utc),[],[])["status"],
                         "not_due_before_initial_cron")
        self.assertEqual(inspect(datetime(2026,11,15,12,tzinfo=timezone.utc),[],[])["status"],
                         "not_due_yet")
    def test_scheduled_cron_not_manual_run(self):
        self.assertEqual(inspect(NOW,[dict(RUN,event="workflow_dispatch")],[])["status"],
                         "missed_scheduled_run")
        self.assertEqual(inspect(NOW,[],[])["status"],"missed_scheduled_run")
    def test_scheduled_scan_requires_verified_discord_receipt(self):
        self.assertEqual(inspect(NOW,[RUN],[])["status"],
                         "scheduled_scan_succeeded_discord_unverified")
        self.assertEqual(inspect(NOW,[RUN],[receipt()])["status"],
                         "scheduled_scan_succeeded_discord_unverified")
        self.assertEqual(inspect(NOW,[RUN],[receipt(),receipt("hockey")])["status"],
                         "scheduled_scan_and_discord_confirmed")
    def test_failure_and_in_progress(self):
        self.assertEqual(inspect(NOW,[dict(RUN,conclusion="failure")],[])["status"],
                         "scheduled_scan_failed")
        self.assertEqual(inspect(NOW,[dict(RUN,status="in_progress",conclusion=None)],[])["status"],
                         "scheduled_scan_in_progress")
    def test_untrusted_receipt_fails(self):
        fake=receipt();fake["user"]["login"]="stranger"
        with self.assertRaisesRegex(ValueError,"Untrusted"):
            inspect(NOW,[RUN],[fake])
if __name__=="__main__":
    unittest.main()
