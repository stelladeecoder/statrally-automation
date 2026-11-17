"""Deliver a current NHL morning slate to the dedicated NHL picks webhook."""
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from nhl_moneyline_ledger_delivery import PUBLIC, RECEIPT, api, reserve, send

CENTRAL = ZoneInfo("America/Chicago")


def render(data, now):
    day = now.astimezone(CENTRAL).date()
    if (data["sport"] != "NHL Moneyline" or data["provider"] != "Kalshi"
        or data["date_central"] != day.isoformat() or data["paper_only"] is not True
        or type(data["orders_placed"]) is not int or data["orders_placed"] != 0):
        raise ValueError("Untrusted morning watchlist")
    fields = []
    seen = set()
    for game in data["fixtures"]:
        fixture = game["fixture_id"]
        if fixture in seen or not re.fullmatch(r"[0-9]+", fixture):
            raise ValueError("Duplicate or invalid NHL fixture")
        seen.add(fixture)
        away, home = game["away"], game["home"]
        if not all(re.fullmatch(r"[A-Z]{2,4}", team) for team in (away, home)):
            raise ValueError("Invalid NHL team code")
        start = datetime.fromisoformat(game["start_central"]).astimezone(CENTRAL)
        if start.date() != day or start <= now:
            raise ValueError("Morning slate contains a stale fixture")
        contracts = game["contracts"]
        verified = game["market_identity_verified"]
        if verified is True:
            if (len(contracts) != 2 or len(set(contracts)) != 2 or
                not all(re.fullmatch(r"KXNHLGAME-[A-Z0-9]+-[A-Z0-9]+", t) for t in contracts)):
                raise ValueError("Invalid matched Kalshi pair")
        elif verified is not False or contracts:
            raise ValueError("Unverified Kalshi market in watchlist")
        opening, closing = (start-timedelta(minutes=offset) for offset in (60, 45))
        fields.append({"name": f"{away} @ {home}",
                       "value": f"Start {start:%I:%M %p %Z} | Entry {opening:%I:%M %p}–{closing:%I:%M %p %Z}\n"
                                + (", ".join(contracts) if verified else "No verified Kalshi contract")})
    if not fields:
        return None
    if len(fields) > 25:
        raise ValueError("NHL slate exceeds Discord embed capacity")
    return {"embeds":[{"title": f"[PAPER WATCHLIST] NHL Moneyline | {day}",
                       "description":"Kalshi | $0 real orders", "color":3447003,
                       "fields":fields}],"allowed_mentions":{"parse":[]}}


def main(path):
    if os.environ.get("STATRALLY_NHL_PAPER_ONLY") != "true":
        raise ValueError("Paper-only mode required")
    now = datetime.now(CENTRAL)
    payload = render(json.loads(Path(path).read_text()), now)
    if payload is None:
        print("No NHL games scheduled")
        return
    webhook = os.environ["STATRALLY_NHL_PICKS_WEBHOOK"]
    if not webhook:
        raise ValueError("NHL picks webhook missing")
    issue = reserve(f"sport=nhl | {now.date()} | morning_watchlist")
    if issue is None:
        print("Morning watchlist already reserved")
        return
    message = send(webhook, payload)
    api("POST", PUBLIC, f"/issues/{issue}/comments", {"body": RECEIPT+json.dumps({
        "state":"CONFIRMED","discord_message_id":message,"paper_only":True,"orders_placed":0})})
    print(f"Morning watchlist Discord message ID {message}")


if __name__ == "__main__":
    main(sys.argv[1])
