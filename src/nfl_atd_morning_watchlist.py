"""Render and deliver a fail-closed NFL Anytime TD PAPER watchlist."""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from nhl_moneyline_ledger_delivery import PUBLIC, api, pages

CENTRAL = ZoneInfo("America/Chicago")
RECEIPT = "statrally-nfl-atd-discord-delivery-v1:"
TICKER = re.compile(r"^KXNFLANYTD-[A-Z0-9-]+$")
MESSAGE_ID = re.compile(r"^[0-9]{15,22}$")


def _time(value):
    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Timestamp missing timezone")
    return stamp.astimezone(timezone.utc)


def _players(fixture):
    if isinstance(fixture.get("players"), list):
        return fixture["players"]
    return fixture.get("contracts", [])


def render(data, now):
    day = now.astimezone(CENTRAL).date()
    if (data.get("schema") not in ("nfl-atd-shadow-v1", "nfl-atd-shadow-live-v2")
        or data.get("sport", "nfl").lower() != "nfl"
        or data.get("market_type") != "atd"
        or data.get("paper_only") is not True
        or type(data.get("orders_placed")) is not int
        or data["orders_placed"] != 0
        or data.get("discord_posts", 0) != 0):
        raise ValueError("Untrusted NFL ATD morning watchlist")

    fixtures = data.get("fixtures", data.get("games"))
    if not isinstance(fixtures, list):
        raise ValueError("NFL fixture slate missing")
    fields = []
    seen_fixtures = set()
    for fixture in fixtures:
        fixture_id = fixture.get("fixture_id")
        if (not isinstance(fixture_id, str) or not fixture_id.strip()
                or fixture_id in seen_fixtures):
            raise ValueError("Duplicate or invalid NFL fixture")
        seen_fixtures.add(fixture_id)
        kickoff = _time(fixture["kickoff_utc"])
        if kickoff <= now.astimezone(timezone.utc):
            raise ValueError("NFL slate contains a stale fixture")
        if kickoff.astimezone(CENTRAL).date() != day:
            raise ValueError("NFL fixture is outside the Central game day")

        contracts = []
        seen_tickers = set()
        for player in _players(fixture):
            ticker = player.get("ticker")
            if (not isinstance(ticker, str) or not TICKER.fullmatch(ticker)
                    or ticker in seen_tickers):
                raise ValueError("Invalid or duplicate NFL ATD ticker")
            seen_tickers.add(ticker)
            if player.get("identity_verified") is not True:
                continue
            if player.get("official_active_verified") is not True:
                continue
            name = player.get("full_name") or player.get("player_id")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Verified NFL player identity missing")
            contracts.append(f"{name} ({ticker})")

        start = kickoff.astimezone(CENTRAL)
        entry_start = start - timedelta(minutes=90)
        entry_end = start - timedelta(minutes=60)
        fields.append({
            "name": fixture_id,
            "value": (
                f"Kickoff {start:%I:%M %p %Z} | Entry "
                f"{entry_start:%I:%M %p}-{entry_end:%I:%M %p %Z}\n"
                + ("\n".join(contracts)
                   if contracts else "No verified active NFL ATD contract")
            ),
        })
    if not fields:
        return None
    if len(fields) > 25:
        raise ValueError("NFL slate exceeds Discord embed capacity")
    return {
        "username": "StatRally NFL ATD",
        "embeds": [{
            "title": f"[PAPER WATCHLIST] NFL ATD | {day}",
            "description": "Kalshi KXNFLANYTD | $0 real orders | inactive checks required",
            "color": 3447003,
            "fields": fields,
            "footer": {"text": "StatRally | NFL ATD | PAPER WATCHLIST | No real orders"},
        }],
        "allowed_mentions": {"parse": []},
    }


def _send(webhook, payload, *, opener=urlopen):
    if not re.fullmatch(
        r"https://(?:discord.com|discordapp.com)/api/webhooks/[0-9]+/[^/]+",
        webhook,
    ):
        raise ValueError("Invalid Discord webhook URL")
    request = Request(
        webhook + ("&" if "?" in webhook else "?") + "wait=true",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "StatRally-Monitor/1",
        },
    )
    try:
        with opener(request, timeout=20) as response:
            status = response.status
            body = response.read()
    except HTTPError as error:
        raise ValueError(
            f"Discord rejected webhook request (HTTP {error.code})"
        ) from None
    message_id = str(json.loads(body).get("id", ""))
    if status != 200 or not MESSAGE_ID.fullmatch(message_id):
        raise ValueError(
            f"Discord delivery not confirmed: HTTP {status}, "
            f"valid ID={bool(message_id)}"
        )
    print(f"Discord delivery: HTTP {status}; Discord message ID {message_id}")
    return message_id


def _reserve(day, *, call=api):
    key = f"sport=nfl-atd | {day} | morning_watchlist"
    title = "NFL ATD PAPER Discord | " + key
    issues = pages(PUBLIC, "/issues?state=all", call=call)
    matches = [
        issue for issue in issues
        if issue.get("title") == title and "pull_request" not in issue
    ]
    if matches:
        if len(matches) != 1 or not str(matches[0].get("body", "")).startswith(RECEIPT):
            raise ValueError("Ambiguous NFL outbound delivery reservation")
        return None
    item = call("POST", PUBLIC, "/issues", {
        "title": title,
        "body": RECEIPT + json.dumps({
            "key": key,
            "state": "RESERVED",
            "paper_only": True,
            "orders_placed": 0,
        }),
    })
    if not item.get("number"):
        raise ValueError("NFL delivery reservation not durable")
    return item["number"]


def main(path):
    if os.environ.get("STATRALLY_NFL_PAPER_ONLY") != "true":
        raise ValueError("Paper-only mode required")
    now = datetime.now(CENTRAL)
    payload = render(json.loads(Path(path).read_text()), now)
    if payload is None:
        print("No NFL games scheduled")
        return
    webhook = os.environ.get("STATRALLY_NFL_PICKS_WEBHOOK", "")
    if not webhook:
        raise ValueError("NFL picks webhook missing")
    issue = _reserve(now.date())
    if issue is None:
        print("NFL morning watchlist already reserved")
        return
    message_id = _send(webhook, payload)
    api("POST", PUBLIC, f"/issues/{issue}/comments", {
        "body": RECEIPT + json.dumps({
            "state": "CONFIRMED",
            "discord_message_id": message_id,
            "paper_only": True,
            "orders_placed": 0,
        }),
    })
    print(f"NFL morning watchlist Discord message ID {message_id}")


if __name__ == "__main__":
    main(sys.argv[1])
