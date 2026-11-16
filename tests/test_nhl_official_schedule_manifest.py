import io
import json
import unittest
from datetime import date
from nhl_paper_recap_scheduler import official_slate

DAY = date(2026, 11, 16)

class Response:
    def __init__(self, value):
        self.data = io.BytesIO(json.dumps(value).encode())
    def __enter__(self):
        return self.data
    def __exit__(self, *args):
        return False

def game(identifier, away="MTL", home="NYR", season=20262027):
    return {"id": identifier, "season": season, "gameDate": "2026-11-16",
            "awayTeam": {"abbrev": away}, "homeTeam": {"abbrev": home}}

def week(games, *, date_string="2026-11-16", count=None):
    day = {"date": date_string, "games": games}
    if count is not None:
        day["numberOfGames"] = count
    return {"gameWeek": [day]}

def read(payload):
    return official_slate(DAY, opener=lambda req, timeout: Response(payload))

class OfficialNhlScheduleTests(unittest.TestCase):
    def test_two_game_slate(self):
        payload = week([game(2026020331), game(2026020332, "VAN", "UTA")], count=2)
        self.assertEqual(read(payload), {"2026020331", "2026020332"})

    def test_legitimate_off_day(self):
        self.assertEqual(read(week([], count=0)), set())

    def test_wrong_season(self):
        with self.assertRaisesRegex(ValueError, "season mismatch"):
            read(week([game(1, season=20252026)], count=1))

    def test_missing_target_date(self):
        with self.assertRaisesRegex(ValueError, "target date"):
            read(week([], date_string="2026-11-17", count=0))

    def test_count_mismatch(self):
        with self.assertRaisesRegex(ValueError, "numberOfGames mismatch"):
            read(week([game(1)], count=2))

    def test_missing_gameweek(self):
        with self.assertRaisesRegex(ValueError, "gameWeek"):
            read({"games": []})

    def test_duplicate_target_date(self):
        payload = week([], count=0)
        payload["gameWeek"].append({"date": "2026-11-16", "games": [], "numberOfGames": 0})
        with self.assertRaisesRegex(ValueError, "target date"):
            read(payload)

    def test_missing_games(self):
        with self.assertRaisesRegex(ValueError, "schedule games"):
            read({"gameWeek": [{"date": "2026-11-16", "numberOfGames": 0}]})

    def test_missing_teams(self):
        bad = game(1)
        del bad["homeTeam"]
        with self.assertRaisesRegex(ValueError, "awayTeam/homeTeam"):
            read(week([bad], count=1))

    def test_duplicate_or_noninteger_id(self):
        with self.assertRaisesRegex(ValueError, "game ID"):
            read(week([game(1), game(1)], count=2))
        with self.assertRaisesRegex(ValueError, "game ID"):
            read(week([game("1")], count=1))

if __name__ == "__main__":
    unittest.main()
