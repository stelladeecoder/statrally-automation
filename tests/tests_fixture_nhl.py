"""Only test-time stand-in for immutable NHL forecast ledger."""
from contextlib import contextmanager
from unittest.mock import patch
from datetime import datetime,timezone

@contextmanager
def dummy():
    fixtures=[{"id":f"espn:hockey:nhl:{i}","league":"nhl",
               "sport":"hockey","category":"men",
               "settlement_basis":"full_game_including_shootout_score",
               "home":f"Home {i}","away":f"Away {i}",
               "home_team_id":str(i+100),"away_team_id":str(i+300),
               "kickoff_utc":"2026-11-14T20:00:00+00:00",
               "forecast":{"status":"research_prediction","p_even":.314815,
                           "p_odd":.685185,"qualified_bet":False}} for i in range(14)]
    report={"schema_version":1,"status":"research_only","market":"TOTAL_SCORE_PARITY",
            "day_central":"2026-11-14","generated_at":"2026-11-14T15:29:47+00:00",
            "models_promoted":False,"markets_verified":False,
            "qualified_bets":0,"trades_placed":0,
            "competitions":[{"league":"nhl","category":"men","competition_name":"NHL",
                             "pregame_count":14,"historical_games":142,"fixtures":fixtures}]}
    with patch("replace_nhl_watchlist_today.build_frozen_nhl_report",return_value=report):
        yield
