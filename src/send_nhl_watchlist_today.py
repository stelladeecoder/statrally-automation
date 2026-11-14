"""One-time reroute of the *already frozen* Nov 14 NHL watchlist to #nhl-watchlist.

No rescanning, no altered probabilities, no soccer delivery and no retries
after an ambiguous Discord send. This is explicitly owner-requested backfill.
"""
import json
import os
from datetime import datetime,timezone,date
from zoneinfo import ZoneInfo
from parity_forward_ledger import issues,verify_issue,TITLE as FORECAST_TITLE
from parity_sport_delivery import pages
from parity_discord import github,discord_send,reservation,RESERVATION
from verify_nhl_watchlist_webhook import verify
from send_nhl_watchlist_test import EXPECTED_CHANNEL_ID

DAY="2026-11-14"
DELIVERY_TITLE="StatRally NHL frozen watchlist in NHL channel | "+DAY

def build_frozen_nhl_report(repo,*,call=github):
    hits=[item for item in issues(repo,call=call)
          if item.get("title")==FORECAST_TITLE+DAY]
    if len(hits)!=1:
        raise ValueError("Expected exactly one original NHL pregame forecast ledger")
    record=verify_issue(hits[0])
    if record["day_central"]!=DAY or record.get("status")!="unpromoted_forward_research":
        raise ValueError("Original forecast snapshot is not verified")
    fixtures=[row for row in record["fixtures"] if row["league"]=="nhl"]
    if len(fixtures)!=14 or len({x["id"] for x in fixtures})!=14:
        raise ValueError("Today's frozen NHL slate is not the expected 14 games")
    if any(row["forecast"]["status"]!="research_prediction"
           or row["forecast"].get("qualified_bet") is not False
           or row.get("settlement_basis")!="full_game_including_shootout_score"
           for row in fixtures):
        raise ValueError("Original NHL probabilities were not approved for read-only rendering")
    return {"schema_version":1,"status":"research_only","market":"TOTAL_SCORE_PARITY",
            "day_central":DAY,"models_promoted":False,"markets_verified":False,
            "qualified_bets":0,"trades_placed":0,"generated_at":record["generated_at"],
            "competitions":[{"league":"nhl","competition_name":"NHL",
                "category":"men","historical_games":0,"pregame_count":len(fixtures),
                "fixtures":fixtures}]}

def send_today(repo,webhook,*,now=None,call=github,sender=discord_send,
               verifier=verify):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.astimezone(ZoneInfo("America/Chicago")).date()!=date.fromisoformat(DAY):
        raise ValueError("One-time NHL delivery is restricted to November 14, 2026 Central")
    if not webhook:
        raise ValueError("Dedicated NHL watchlist webhook not configured")
    check=verifier(webhook,"")
    if check.get("verified") is not True or str(check.get("channel_id"))!=EXPECTED_CHANNEL_ID:
        raise ValueError("Dedicated NHL watchlist destination is not verified")
    report=build_frozen_nhl_report(repo,call=call)
    payloads=pages(report,"hockey")
    if len(payloads)!=1:
        raise ValueError("Expected one complete NHL watchlist Discord message")
    # Explicitly state when the original research baseline was issued.
    issued=datetime.fromisoformat(report["generated_at"].replace("Z","+00:00"))
    embed=payloads[0]["embeds"][0]
    embed["title"]="🏒 NHL EVEN/ODD | "+DAY+" | #nhl-watchlist"
    embed["footer"]["text"]=(
       "14 NHL games · Frozen research estimate from Nov 14 "
       +issued.strftime("%H:%M UTC")
       +" · NOT approved betting picks · No live prices"
    )
    # One unique reservation to deliberately cross-post an already delivered
    # general-channel research report into the user's newly configured channel.
    reservation_issue=reservation(repo,DELIVERY_TITLE,call=call)
    if reservation_issue is None:
        return {"status":"already_reserved_no_resend","sent":False}
    message_id=sender(webhook,payloads[0])
    response=call("PATCH",repo,f"/issues/{reservation_issue}",{
       "state":"closed",
       "body":RESERVATION+json.dumps({"status":"confirmed","key":DELIVERY_TITLE,
           "message_id":message_id,"channel_id":EXPECTED_CHANNEL_ID,
           "count":14,"issued_at":report["generated_at"]},sort_keys=True)})
    if response.get("number")!=reservation_issue:
        raise ValueError("Discord accepted watchlist, but receipt save was not confirmed")
    return {"status":"confirmed","sent":True,
            "message_id":message_id,"channel_id":EXPECTED_CHANNEL_ID,
            "games":14}

if __name__=="__main__":
    result=send_today(os.environ["GITHUB_REPOSITORY"],
           os.environ.get("STATRALLY_NHL_WATCHLIST_WEBHOOK",""))
    print("NHL_WATCHLIST_TODAY="+json.dumps(result,sort_keys=True))
