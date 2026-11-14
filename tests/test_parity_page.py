import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from build_public_dashboard import build

class ParityPageTests(unittest.TestCase):
    def test_pages_site_contains_parity_separate_from_btts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            build(root)
            self.assertTrue((root/"parity.html").is_file())
            self.assertTrue((root/"parity-web.mjs").is_file())
            self.assertIn("parity.html",(root/"index.html").read_text())
            self.assertIn('fetch("./parity.json"',(root/"parity-web.mjs").read_text())
            self.assertIn("BTTS",(root/"index.html").read_text())
if __name__=="__main__":
    unittest.main()
