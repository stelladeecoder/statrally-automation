import io
import json
import unittest
import zipfile
from datetime import datetime,timedelta,timezone
from parity_model_handoff_consumer import validate,retrieve,record,PRIVATE,LEAGUES,CONTRACT,PREFIX
NOW=datetime(2026,11,14,17,0,tzinfo=timezone.utc)
def source():
    return {"schema_version":1,"contract":CONTRACT,
        "source_repository":PRIVATE,"source_commit":"a"*40,"source_run_id":1234,
        "input_repository":"stelladeecoder/statrally-automation",
        "input_day":"2026-11-14","input_issued_at":"2026-11-14T15:00:00+00:00",
        "exported_at":"2026-11-14T16:30:00+00:00",
        "model":"team_poisson_parity_candidate_v1",
        "status":"research_only_not_promoted","validated_for_production":False,
        "calibrated":False,"markets_verified":False,"qualified_bets":0,"trades_placed":0,
        "forecasts":[{"id":"espn:soccer:eng.1:123","league":"soccer_epl",
          "status":"research_forecast_not_promoted","model":"team_poisson_parity_candidate_v1",
          "calibrated":False,"market_verified":False,"qualified_bet":False,
          "p_even":.5012,"p_odd":.4988,"issued_at":"2026-11-14T16:30:00+00:00",
          "kickoff_utc":"2026-11-14T19:00:00+00:00"}],
        "holdout_by_league":{k:{"status":"research_only_not_promoted",
          "evaluated":20,"candidate_brier":.25,"calibrated":False,"promoted":False}
          for k in LEAGUES}}
def run():
    return {"id":1234,"head_sha":"a"*40,"head_branch":"main","status":"completed",
            "conclusion":"success","event":"schedule",
            "created_at":"2026-11-14T16:00:00+00:00"}
class HandoffConsumerTests(unittest.TestCase):
    def test_full_success_is_still_not_promoted(self):
        projection=validate(source(),run(),now=NOW)
        self.assertEqual(projection["source_run_id"],1234)
        self.assertEqual(len(projection["forecasts"]),1)
        self.assertFalse(projection["production_enabled"])
        self.assertEqual(projection["qualified_bets"],0)
    def test_reject_unverified_bet_or_modified_source_sha(self):
        bad=source()
        bad["qualified_bets"]=1
        with self.assertRaisesRegex(ValueError,"promotion"):
            validate(bad,run(),now=NOW)
        bad=source()
        bad["source_commit"]="b"*40
        with self.assertRaisesRegex(ValueError,"provenance"):
            validate(bad,run(),now=NOW)
    def test_reject_post_kickoff_forged_or_stale(self):
        bad=source()
        bad["forecasts"][0]["kickoff_utc"]="2026-11-14T16:00:00+00:00"
        with self.assertRaisesRegex(ValueError,"Post-kickoff"):
            validate(bad,run(),now=NOW)
        with self.assertRaisesRegex(ValueError,"Stale"):
            validate(source(),run(),now=NOW+timedelta(days=3))
        bad=source()
        bad["forecasts"][0]["status"]="team_identity_unconfirmed"
        with self.assertRaisesRegex(ValueError,"Unverified"):
            validate(bad,run(),now=NOW)
    def test_reject_missing_league_evidence(self):
        bad=source()
        bad["holdout_by_league"].pop("soccer_mls")
        with self.assertRaisesRegex(ValueError,"coverage"):
            validate(bad,run(),now=NOW)
    def test_retrieve_validates_private_workflow_artifact_and_zip(self):
        def get(url,token,binary=False):
            if "/runs?branch=" in url:return {"workflow_runs":[run()]}
            if "/artifacts?per_page=" in url:
                return {"artifacts":[{"id":999,"name":"statrally-model-handoff-1234",
                         "expired":False}]}
            if "/artifacts/999/zip" in url:
                stream=io.BytesIO()
                with zipfile.ZipFile(stream,"w") as z:
                    z.writestr("model-handoff.json",json.dumps(source()))
                return stream.getvalue()
            raise AssertionError(url)
        result=retrieve("private-token-only",get=get,now=NOW)
        self.assertEqual(result["source_run_id"],1234)
    def test_deduplicate_public_research_evidence(self):
        projection=validate(source(),run(),now=NOW)
        seen=[]
        def call(method,repo,path,data=None):
            if method=="GET":return seen
            if method=="POST":
                doc={"number":777,"title":data["title"],"body":data["body"],
                     "user":{"login":"github-actions[bot]"}}
                seen.append(doc)
                return doc
            raise AssertionError(method)
        self.assertEqual(record("o/r",projection,call=call)["status"],"recorded")
        self.assertEqual(record("o/r",projection,call=call)["status"],"already_recorded")
if __name__=="__main__":
    unittest.main()
