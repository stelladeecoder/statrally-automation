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
    def test_wrong_season_rejected(self):
        payload={"games":[{"id":1,"season":20252026,"gameDate":"2026-11-16"}]}
        with self.assertRaisesRegex(ValueError,"season mismatch"):
            official_slate(date(2026,11,16),opener=lambda req,timeout:Response(payload))
    def test_valid_off_day_is_empty(self):
        self.assertEqual(official_slate(date(2026,11,16),
            opener=lambda req,timeout:Response({"games":[] })),set())
    def test_complete_two_game_slate(self):
        payload={"games":[{"id":2026020331,"season":20262027,"gameDate":"2026-11-16"},
                          {"id":2026020332,"season":20262027,"gameDate":"2026-11-16"}]}
        self.assertEqual(len(official_slate(date(2026,11,16),
            opener=lambda req,timeout:Response(payload))),2)
    def test_missing_games_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"game data"):
            official_slate(date(2026,11,16), opener=lambda req,timeout:Response({}))


if __name__=="__main__":
    unittest.main()
