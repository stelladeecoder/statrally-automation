"""Deliver a fail-closed NFL anytime-touchdown paper slate."""
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from nhl_moneyline_ledger_delivery import PUBLIC, RECEIPT, api, reserve, send

CENTRAL = ZoneInfo("America/Chicago")
TICKER = re.compile(r"KXNFLANYTD-[A-Z0-9-]+")


def render(data, now):
    day = now.astimezone(CENTRAL).date()
    if (data.get("sport") != "NFL ATD" or data.get("provider") != "Kalshi"
        or data.get("date_central") != day.isoformat()
        or data.get("paper_only") is not True
        or type(data.get("orders_placed")) is not int
        or data["orders_placed"] != 0):
        raise ValueError("Untrusted NFL morning watchlist")
    fields = []
    seen = set()
    for game in data.get("fixtures", []):
        fixture = game.get("fixture_id")
        if (not isinstance(fixture, str) or fixture in seen
                or not re.fullmatch(r"[0-9]+", fixture)
                or game.get("fixture_verified") is not True):
            raise ValueError("Duplicate or unverified NFL fixture")
        seen.add(fixture)
        away, home = game.get("away"), game.get("home")
        if not all(isinstance(team, str) and re.fullmatch(r"[A-Z]{2,4}", team)
                   for team in (away, home)):
            raise ValueError("Invalid NFL team code")
        start = datetime.fromisoformat(game["start_central"]).astimezone(CENTRAL)
        if start.date() != day or start <= now:
            raise ValueError("Morning slate contains a stale fixture")
        players = game.get("players", [])
        if not isinstance(players, list):
            raise ValueError("Invalid NFL player slate")
        lines = []
        player_ids = set()
        for player in players:
            player_id = player.get("player_id")
            if not isinstance(player_id, str) or not player_id or player_id in player_ids:
                raise ValueError("Duplicate or missing NFL player")
            player_ids.add(player_id)
            if player.get("inactive_checked") is not True:
                raise ValueError("NFL inactive status not checked")
            ticker = player.get("contract")
            verified = player.get("market_identity_verified")
            if verified is True:
                if not isinstance(ticker, str) or not TICKER.fullmatch(ticker):
                    raise ValueError("Invalid matched NFL Kalshi contract")
                label = ticker
            elif verified is False and not ticker:
                label = "UNMATCHED/NO VERIFIED CONTRACT"
            else:
                raise ValueError("Unverified NFL Kalshi market in watchlist")
            name = player.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("NFL player name missing")
            lines.append(f"{name} — {label}")
        if not lines:
            lines.append("No active NFL ATD players verified")
        entry = start - timedelta(minutes=90)
        fields.append({
            "name": f"{away} @ {home}",
            "value": (f"Start {start:%I:%M %p %Z} | Planned entry T-90 "
                      f"({entry:%I:%M %p %Z})\n" + "\n".join(lines)),
        })
    if len(fields) > 25:
        raise ValueError("NFL slate exceeds Discord embed capacity")
    return {"embeds": [{
        "title": f"[PAPER WATCHLIST] NFL ATD | {day}",
        "description": ("Kalshi | Active-player ATD contracts | $0 real orders"
                        if fields else
                        "Kalshi | No NFL games scheduled | $0 real orders"),
        "color": 3447003, "fields": fields,
    }], "allowed_mentions": {"parse": []}}


def main(path):
    if os.environ.get("STATRALLY_NFL_PAPER_ONLY") != "true":
        raise ValueError("Paper-only mode required")
    now = datetime.now(CENTRAL)
    payload = render(json.loads(Path(path).read_text()), now)
    webhook = os.environ["STATRALLY_NFL_PICKS_WEBHOOK"]
    if not webhook:
        raise ValueError("NFL picks webhook missing")
    issue = reserve(f"sport=nfl-atd | {now.date()} | morning_watchlist",
                    title_prefix="NFL PAPER Discord | ")
    if issue is None:
        print("Morning watchlist already reserved")
        return
    message = send(webhook, payload)
    api("POST", PUBLIC, f"/issues/{issue}/comments", {"body": RECEIPT + json.dumps({
        "state": "CONFIRMED", "discord_message_id": message,
        "paper_only": True, "orders_placed": 0})})
    print(f"Morning watchlist Discord message ID {message}")


if __name__ == "__main__":
    main(sys.argv[1])
