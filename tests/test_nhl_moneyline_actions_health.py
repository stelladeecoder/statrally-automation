"""Safe existing-credential bridge for private read-only NHL daily health artifacts."""
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import nhl_moneyline_actions_health as m

DAY="2026-11-15"
def report():
    return dict(schema=m.SCHEMA,date_central=DAY,source_repository=m.REPO,
        paper_only=True,orders_placed=0,status="verified_receipts",
        poll_runs_observed=12,scheduled_polls_observed=11,
        scheduled_polls_expected=16,unconfirmed_scheduled_polls=5,
        entry_hits=2,entry_misses_observed=1,
        close_hits=1,close_misses_observed=2,
        kalshi_api_skips=3,low_liquidity_skips=4,
        model_source_errors=0,identity_skips=1,poll_failures=0)
def artifact_bytes(summary):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,"w") as zip:
        zip.writestr(m.FILE,json.dumps(summary))
    return buffer.getvalue()
class TestActionsHealth(unittest.TestCase):
    def test_one_private_actions_artifact_is_verified(self):
        calls=[]
        def fake(url,token,*,binary=False):
            calls.append(url)
            if "artifacts?" in url:
                return {"artifacts":[{"id":99,"name":m.PREFIX+"99","expired":False}]}
            if url.endswith("/99/zip"):
                return artifact_bytes(report())
            raise AssertionError(url)
        data=m.load(DAY,token="masked",request=fake)
        self.assertEqual(data["entry_hits"],2)
        self.assertEqual(len(calls),2)
        self.assertIn("Entry snapshot contract hits/misses: 2/1",
                      m.lines_for_day(DAY,token="masked",loader=lambda *_args,**kw: data))

    def test_other_day_returns_unavailable_not_zero(self):
        def fake(url,token,*,binary=False):
            if "artifacts?" in url:
                return {"artifacts":[{"id":99,"name":m.PREFIX+"99","expired":False}]}
            return artifact_bytes(report())
        self.assertIsNone(m.load("2026-11-14",token="masked",request=fake))
        self.assertIn("UNKNOWN",m.lines_for_day(DAY,token="masked",loader=lambda *_args,**kw: None)[0])

    def test_untrusted_reports_fail(self):
        item=report()
        item["orders_placed"]=1
        with self.assertRaises(ValueError):m.validate(item,DAY)

    def test_missing_actions_token_transparently_unknown(self):
        self.assertIn("MISSING",m.lines_for_day(DAY,token="")[0])

    def test_errors_never_echo_credentials(self):
        token="private-and-secret"
        def bad(*args,**kwargs):raise RuntimeError(token)
        lines=m.lines_for_day(DAY,token=token,loader=bad)
        self.assertIn("ARTIFACT READ ERROR",lines[0])
        self.assertNotIn(token,lines[0])

if __name__=="__main__":unittest.main()
