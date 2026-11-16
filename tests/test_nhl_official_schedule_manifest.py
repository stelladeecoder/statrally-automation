import io
import json
import unittest
from datetime import date
from nhl_paper_recap_scheduler import official_slate


class Response:
    def __init__(self, value):
        self.data = io.BytesIO(json.dumps(value).encode())
    def __enter__(self): return self.data
    def __exit__(self, *args): return False


class OfficialNhlScheduleTests(unittest.TestCase):
    def test_stale_season_is_not_an_off_day(self):
        payload={"regularSeasonStartDate":"2025-10-07",
                 "regularSeasonEndDate":"2026-04-17",
                 "gameWeek":[{"date":"2026-11-16","games":[]}]}
        with self.assertRaisesRegex(ValueError,"does not cover requested season"):
            official_slate(date(2026,11,16),opener=lambda req,timeout:Response(payload))
    def test_valid_off_day_is_empty(self):
        payload={"regularSeasonStartDate":"2026-10-01",
                 "regularSeasonEndDate":"2027-04-01",
                 "gameWeek":[{"date":"2026-11-16","games":[]}]}
        self.assertEqual(official_slate(date(2026,11,16),
            opener=lambda req,timeout:Response(payload)),set())


if __name__=="__main__":
    unittest.main()
