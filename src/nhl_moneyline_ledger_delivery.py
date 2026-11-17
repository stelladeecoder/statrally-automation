"""Fail-closed bridge from private immutable NHL PAPER Issues to Discord.

Reservations precede network sends: ambiguous HTTP outcomes stay quarantined.
Never imports trading clients, backfills observations, or invents settlements.
"""
import json
import os
from decimal import Decimal, InvalidOperation
import re
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import quote
from zoneinfo import ZoneInfo

PRIVATE = "stelladeecoder/statrally-even-odd-models"
PUBLIC = "stelladeecoder/statrally-automation"
PREFIX = "statrally-nhl-moneyline-paper-v1:"
RECEIPT = "statrally-nhl-discord-delivery-v1:"
CHANNELS = {"watchlist": "STATRALLY_NHL_WATCHLIST_WEBHOOK",
            "picks": "STATRALLY_NHL_PICKS_WEBHOOK",
            "results": "STATRALLY_NHL_RESULTS_WEBHOOK"}
TICKER = re.compile(r"^KXNHLGAME-[A-Z0-9-]+$")
ET = ZoneInfo("America/New_York")


def stamp(s):
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("Timestamp missing timezone")
    return d.astimezone(timezone.utc)


def api(method, repo, path, data=None, *, opener=urlopen):
    if repo not in (PRIVATE, PUBLIC) or not path.startswith("/issues"):
        raise ValueError("Restricted to paper ledger and delivery issues")
    token = os.environ["STATRALLY_NHL_LEDGER_TOKEN"]
    headers = {"Authorization": "Bearer " + token,
               "Accept": "application/vnd.github+json",
               "Content-Type": "application/json"}
    request = Request("https://api.github.com/repos/" + repo + path,
                      method=method, headers=headers,
                      data=json.dumps(data).encode() if data is not None else None)
    with opener(request, timeout=20) as response:
        return json.load(response)


def pages(repo, path, *, call=api):
    rows = []
    for page in range(1, 21):
        separator = "&" if "?" in path else "?"
        batch = call("GET", repo, path + separator + "per_page=100&page=" + str(page))
        rows.extend(batch)
        if len(batch) < 100:
            return rows
    raise ValueError("Pagination limit exceeded: refusing incomplete dedup")


def eligible(entry, close=None, settlement=None, *, now=None):
    now = now or datetime.now(timezone.utc)
    if (entry.get("schema_version") != "nhl-kalshi-moneyline-paper-v1"
        or entry.get("paper_trade") is not True or entry.get("orders_placed") != 0
        or entry.get("stage") != "entry"
        or not TICKER.fullmatch(entry.get("market_ticker", ""))):
        raise ValueError("Untrusted paper entry")
    # A real quote is not automatically an approved paper pick.
    if entry.get("signal") not in ("BUY_YES", "QUALIFIED"):
        raise ValueError("No approved paper pick signal")
    if (entry.get("effective_fee_verified") is not True
        or entry.get("fee_exceptions_verified") is not True
        or entry.get("account_fill_fee", "missing") is not None
        or entry.get("paper_fee_execution_assumption") != "taker_crossing_ask"):
        raise ValueError("Unverified effective paper fee")
    try:
        edge = Decimal(str(entry["post_fee_edge"]))
        fee = Decimal(str(entry["scheduled_paper_fee_dollars"]))
        price = Decimal(str(entry["ask_dollars"]))
        probability = Decimal(str(entry["model_probability"]))
    except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Missing or invalid paper edge inputs") from exc
    if not (edge.is_finite() and fee.is_finite() and price.is_finite()
            and probability.is_finite() and 0 < price < 1
            and 0 < probability < 1 and fee >= 0
            and edge > 0 and abs(edge - (probability - price - fee)) <= Decimal("0.000001")):
        raise ValueError("Nonpositive or inconsistent post-fee paper edge")
    start, observed, forecast = map(stamp, (entry["game_start_utc"],
        entry["observed_utc"], entry["model_forecast_created_utc"]))
    if not (45 <= (start-observed).total_seconds()/60 <= 60
            and forecast <= observed <= now
            and entry.get("market_identity_verified") is True
            and entry.get("snapshot_sha256")
            and entry.get("fixture_source_id")
            and entry.get("orderbook_source")):
        raise ValueError("Unverified prospective entry")
    if close is not None:
        if not same(entry, close) or close.get("stage") != "close":
            raise ValueError("Close contract mismatch")
        closing = stamp(close["observed_utc"])
        if not (0 <= (start-closing).total_seconds()/60 <= 5
                and observed < closing <= now and close.get("snapshot_sha256")
                and close.get("market_identity_verified") is True):
            raise ValueError("Unverified closing snapshot")
    if settlement is not None:
        if close is None or not same(entry, settlement) or settlement.get("stage") != "settlement":
            raise ValueError("Settlement contract mismatch")
        if not (stamp(settlement["observed_utc"]) > start
                and stamp(settlement["observed_utc"]) <= now
                and settlement.get("settlement_verified") is True
                and settlement.get("settlement_source")
                and settlement.get("account_fill_fee", "missing") is None
                and settlement.get("scheduled_paper_fee_dollars") is not None
                and settlement.get("settlement_fee_dollars") == "0.00"
                and settlement.get("post_fee_paper_pnl_dollars") is not None):
            raise ValueError("No verified official settlement and effective fee")
    return True


def same(a, b):
    return all(a.get(k) == b.get(k) for k in
               ("fixture_id", "market_ticker", "game_start_utc", "fixture_source_id"))


def records(issue, *, call=api):
    if not str(issue.get("body", "")).startswith(PREFIX):
        return None
    stages = {}
    for comment in pages(PRIVATE, "/issues/" + str(issue["number"]) + "/comments", call=call):
        body = comment.get("body", "")
        if not body.startswith(PREFIX):
            continue
        row = json.loads(body[len(PREFIX):])
        stage = row.get("stage")
        if stage in ("watchlist", "entry", "close", "settlement"):
            if stage in stages:
                raise ValueError("Duplicate immutable stage in private issue")
            stages[stage] = row
    return stages


def candidates(*, now=None, call=api):
    now = now or datetime.now(timezone.utc)
    # Read the private ledger, never rely on a public untrusted event payload.
    for issue in pages(PRIVATE, "/issues?state=all", call=call):
        if not issue.get("title", "").startswith("StatRally NHL Moneyline PAPER | "):
            continue
        stages = records(issue, call=call)
        if not stages:
            continue
        watch = stages.get("watchlist")
        if watch is not None:
            if (watch.get("schema_version") != "nhl-kalshi-moneyline-paper-v1"
                or watch.get("paper_trade") is not True
                or watch.get("orders_placed") != 0
                or watch.get("stage") != "watchlist"
                or watch.get("fixture_only") is not True
                or watch.get("market_identity_verified") is not True
                or not TICKER.fullmatch(watch.get("market_ticker", ""))
                or not watch.get("fixture_source_id")
                or stamp(watch["observed_utc"]) >= stamp(watch["game_start_utc"])
                or stamp(watch["observed_utc"]) > now):
                raise ValueError("Unverified prospective fixture-only watchlist")
            yield "watchlist", watch, stages
        entry = stages.get("entry")
        if entry is None:
            continue
        if entry.get("signal") not in ("BUY_YES", "QUALIFIED"):
            continue  # NO BET is silent in picks, including unconfirmed fee.
        eligible(entry, now=now)
        yield "picks", entry, stages
        if "settlement" in stages:
            eligible(entry, stages.get("close"), stages["settlement"], now=now)
            yield "results", entry, stages


def reserve(key, *, call=api):
    title = "NHL PAPER Discord | " + key
    issues = pages(PUBLIC, "/issues?state=all", call=call)
    matches = [i for i in issues if i.get("title") == title and "pull_request" not in i]
    if matches:
        if len(matches) != 1 or not str(matches[0].get("body", "")).startswith(RECEIPT):
            raise ValueError("Ambiguous outbound delivery reservation")
        return None
    item = call("POST", PUBLIC, "/issues", {"title": title,
        "body": RECEIPT + json.dumps({"key": key, "state": "RESERVED",
            "paper_only": True, "orders_placed": 0})})
    if not item.get("number"):
        raise ValueError("Delivery reservation not durable")
    return item["number"]


def send(webhook, payload, *, opener=urlopen):
    if not webhook.startswith("https://discord.com/api/webhooks/"):
        raise ValueError("Invalid Discord webhook URL")
    request = Request(webhook + ("&" if "?" in webhook else "?") + "wait=true",
                      data=json.dumps(payload).encode(), method="POST",
                      headers={"Content-Type": "application/json"})
    with opener(request, timeout=20) as response:
        if response.status not in (200, 204):
            raise ValueError("Discord did not acknowledge delivery")
        body = response.read()
        obj = json.loads(body) if body else {}
        if not str(obj.get("id", "")).isdigit():
            raise ValueError("No Discord message ID; ambiguous delivery")
        return str(obj["id"])


def publish(stage, entry, stages, *, call=api, sender=send):
    key = entry["market_ticker"] + " | " + stage
    issue = reserve(key, call=call)
    if issue is None:
        return {"key": key, "state": "already_reserved"}
    text = ("**NHL MONEYLINE [PAPER TRADE]**\\n"
            + "**Contract:** \\u0060" + entry["market_ticker"] + "\\u0060\\n"
            + "**Fixture ID:** " + entry["fixture_id"] + "\\n"
            + "**Puck drop (UTC):** " + entry["game_start_utc"] + "\\n"
            + "**Real orders:** 0\\n")
    if stage == "watchlist":
        text += "**Verified:** Fixture, exact team-YES contract and prospective source"
    elif stage == "picks":
        text += ("**Entry observed (UTC):** " + entry["observed_utc"]
                 + "\\n**Executable ask:** $" + str(entry["ask_dollars"])
                 + "\\n**Status:** PAPER taker-crossing entry; scheduled fee $" + str(entry.get("scheduled_paper_fee_dollars", "unavailable")) + " (no account fill)")
    else:
        result = stages["settlement"]
        text += ("**Closing observed (UTC):** " + stages["close"]["observed_utc"]
                 + "\\n**Official settlement:** " + str(result["winning_team"])
                 + "\\n**Post-fee PAPER P&L:** $" + str(result["post_fee_paper_pnl_dollars"]))
    payload = {"embeds": [{"title": "StatRally NHL | " + stage.upper(),
                          "description": text, "color": {"watchlist": 3447003,
                          "picks": 1752220, "results": 3066993}[stage]}],
               "allowed_mentions": {"parse": []}}
    try:
        message_id = sender(os.environ[CHANNELS[stage]], payload)
    except Exception as exc:
        call("POST", PUBLIC, "/issues/" + str(issue) + "/comments",
             {"body": RECEIPT + json.dumps({"key": key, "state": "AMBIGUOUS_OR_FAILED",
                "error_type": type(exc).__name__, "manual_review_required": True})})
        return {"key": key, "state": "AMBIGUOUS_OR_FAILED"}
    call("POST", PUBLIC, "/issues/" + str(issue) + "/comments",
         {"body": RECEIPT + json.dumps({"key": key, "state": "CONFIRMED",
            "discord_message_id": message_id, "paper_only": True})})
    return {"key": key, "state": "CONFIRMED"}


def main():
    if os.environ.get("STATRALLY_NHL_PAPER_ONLY") != "true":
        raise ValueError("Paper-only gate required")
    results = []
    for stage, entry, stages in candidates():
        results.append(publish(stage, entry, stages))
    print(json.dumps({"paper_only": True, "orders_placed": 0,
                      "delivery_enabled": True, "results": results}, sort_keys=True))


if __name__ == "__main__":
    main()
