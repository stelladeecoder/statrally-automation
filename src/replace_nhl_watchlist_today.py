"""Replace Nov 14 NHL watchlist post with schedule-only post in same Discord channel.

Source is the frozen Nov 14 forecast ledger: game names/start times are NOT
recalculated after start. The new message is posted once, then original is
deleted via the same webhook. Never silently retry a potentially delivered
message.
"""
import json
import os
from datetime import datetime,timezone,date
from urllib.request import Request,urlopen
from urllib.parse import urlsplit,urlunsplit
from zoneinfo import ZoneInfo

from parity_discord import github,discord_send,reservation,RESERVATION
from parity_sport_delivery import pages
from send_nhl_watchlist_today import build_frozen_nhl_report,DAY
from send_nhl_watchlist_test import EXPECTED_CHANNEL_ID
from verify_nhl_watchlist_webhook import verify

OLD_MESSAGE_ID="1571198349707583490"
ISSUE_TITLE="StatRally replace NHL watchlist percentages | "+DAY

def message_url(webhook,message_id):
    parts=urlsplit(webhook)
    if (parts.scheme!="https" or parts.hostname not in ("discord.com","discordapp.com")
        or not parts.path.startswith("/api/webhooks/")
        or parts.username or parts.password or not message_id.isdigit()):
        raise ValueError("Invalid NHL webhook or message ID")
    base=parts.path.rstrip("/")
    return urlunsplit((parts.scheme,parts.netloc,base+"/messages/"+message_id,"",""))

def old_message(webhook,*,opener=urlopen):
    req=Request(message_url(webhook,OLD_MESSAGE_ID),headers={"Accept":"application/json",
                  "User-Agent":"StatRally-NHL-Watchlist-Replace/1"})
    with opener(req,timeout=18) as response:
        if response.status!=200:
            raise ValueError("Original Discord message not retrievable")
        message=json.load(response)
    if (not isinstance(message,dict) or str(message.get("id"))!=OLD_MESSAGE_ID
        or str(message.get("channel_id"))!=EXPECTED_CHANNEL_ID
        or not isinstance(message.get("embeds"),list)
        or not any("NHL EVEN/ODD" in x.get("title","") and
                   "2026-11-14" in x.get("title","") for x in message["embeds"])):
        raise ValueError("Original NHL message identity/channel mismatch")
    return True

def delete_old(webhook,*,opener=urlopen):
    req=Request(message_url(webhook,OLD_MESSAGE_ID),method="DELETE",
                headers={"User-Agent":"StatRally-NHL-Watchlist-Replace/1"})
    with opener(req,timeout=18) as response:
        if response.status!=204:
            raise ValueError("Discord did not confirm deletion")
    return True

def replace(repo,webhook,*,now=None,call=github,sender=discord_send,
            verifier=verify,old_checker=old_message,deleter=delete_old):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.astimezone(ZoneInfo("America/Chicago")).date()!=date.fromisoformat(DAY):
        raise ValueError("Replacement is restricted to Nov 14 Central date")
    if not webhook:
        raise ValueError("Missing dedicated NHL watchlist webhook")
    info=verifier(webhook,"")
    if info.get("verified") is not True or str(info.get("channel_id"))!=EXPECTED_CHANNEL_ID:
        raise ValueError("Dedicated NHL watchlist channel not verified")
    report=build_frozen_nhl_report(repo,call=call)
    payloads=pages(report,"hockey")
    if len(payloads)!=1:
        raise ValueError("Expected exactly one complete NHL watchlist page")
    payload=payloads[0]
    embed=payload["embeds"][0]
    embed["title"]="🏒 NHL Watchlist | "+DAY+" | #nhl-watchlist"
    embed["footer"]["text"]="14 NHL games · Matchups & start times only · Probabilities/odds only in qualified #nhl-picks"
    body=embed["description"]
    if ("%" in body or "EVEN " in body or "ODD " in body or
        sum(body.count("• "+x["away"]+" @ "+x["home"]+" · ") for x in report["competitions"][0]["fixtures"])!=14):
        raise ValueError("Watchlist contains probabilities or omits matchups")
    # Verify the exact existing message before reserving and sending a replacement.
    old_checker(webhook)
    number=reservation(repo,ISSUE_TITLE,call=call)
    if number is None:
        return {"status":"previously_reserved_no_resend","sent":False}
    new_id=sender(webhook,payload)
    if not str(new_id).isdigit():
        raise ValueError("New Discord receipt not confirmed")
    first=call("PATCH",repo,f"/issues/{number}",{
        "body":RESERVATION+json.dumps({"key":ISSUE_TITLE,
            "status":"new_message_confirmed_old_pending_deletion",
            "new_message_id":str(new_id),"old_message_id":OLD_MESSAGE_ID},sort_keys=True)})
    if first.get("number")!=number:
        raise ValueError("Replacement sent but receipt save failed: do not retry")
    deleter(webhook)
    final=call("PATCH",repo,f"/issues/{number}",{"state":"closed",
        "body":RESERVATION+json.dumps({"key":ISSUE_TITLE,"status":"confirmed",
          "new_message_id":str(new_id),"old_message_id":OLD_MESSAGE_ID,
          "old_deleted":True,"game_count":14},sort_keys=True)})
    if final.get("number")!=number:
        raise ValueError("Discord replacement completed but final receipt save failed")
    return {"status":"confirmed","sent":True,"games":14,
            "new_message_id":str(new_id),"old_deleted":True}

if __name__=="__main__":
    result=replace(os.environ["GITHUB_REPOSITORY"],
         os.environ.get("STATRALLY_NHL_WATCHLIST_WEBHOOK",""))
    print("NHL_WATCHLIST_REPLACEMENT="+json.dumps(result,sort_keys=True))
