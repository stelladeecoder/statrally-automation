"""Preview verified NHL paper trade summaries for each official slate."""
import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from nhl_moneyline_ledger_delivery import (
    PRIVATE, PUBLIC, api, pages, records, stamp, reserve, send, eligible, RECEIPT
)

ET = ZoneInfo("America/New_York")
CT = ZoneInfo("America/Chicago")
FIRST_RECAP = datetime(2026, 11, 16).date()
BASE = "https://api-web.nhle.com/v1/schedule/"


def official_slate(day, *, opener=urlopen):
    """Require one exact ET date in the NHL weekly schedule, failing closed."""
    if not ("2026-09-18" <= day.isoformat() <= "2027-04-11"):
        raise ValueError("Requested date outside validated 2026-27 season bounds")
    url = BASE + day.isoformat()
    with opener(Request(url, method="GET",
                        headers={"Accept": "application/json",
                                 "User-Agent": "statrally-automation/1.0"}),
                timeout=20) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or not isinstance(payload.get("gameWeek"), list):
        raise ValueError("Missing NHL schedule gameWeek")
    matches = [item for item in payload["gameWeek"]
               if isinstance(item, dict) and item.get("date") == day.isoformat()]
    if len(matches) != 1:
        raise ValueError("Missing or duplicate target date in NHL gameWeek")
    slate = matches[0]
    games = slate.get("games")
    if not isinstance(games, list):
        raise ValueError("Missing NHL schedule games")
    if "numberOfGames" in slate:
        count = slate["numberOfGames"]
        if type(count) is not int or count != len(games):
            raise ValueError("NHL schedule numberOfGames mismatch")
    ids = set()
    for game in games:
        if not isinstance(game, dict) or str(game.get("season")) != "20262027":
            raise ValueError("NHL schedule season mismatch")
        start = game.get("startTimeUTC")
        if not isinstance(start, str):
            raise ValueError("Missing NHL startTimeUTC")
        try:
            parsed = datetime.fromisoformat(start.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
                raise ValueError("NHL startTimeUTC must be UTC")
            game_et_day = parsed.astimezone(ET).date()
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("Invalid NHL startTimeUTC") from exc
        if game_et_day != day:
            raise ValueError("NHL startTimeUTC Eastern date mismatch")
        if game.get("gameDate") is not None and str(game["gameDate"])[:10] != day.isoformat():
            raise ValueError("NHL schedule game date mismatch")
        game_id = game.get("id")
        if type(game_id) is not int or game_id in ids:
            raise ValueError("Missing, noninteger or duplicate NHL game ID")
        if not isinstance(game.get("awayTeam"), dict) or not isinstance(game.get("homeTeam"), dict):
            raise ValueError("Missing NHL awayTeam/homeTeam")
        ids.add(game_id)
    return {str(game_id) for game_id in ids}


def ledger(*, call=api):
    by_game = defaultdict(list)
    for issue in pages(PRIVATE, "/issues?state=all", call=call):
        if not str(issue.get("title", "")).startswith("StatRally NHL Moneyline PAPER | "):
            continue
        stages = records(issue, call=call)
        if not stages or "watchlist" not in stages:
            continue
        watch = stages["watchlist"]
        if watch.get("fixture_only") is not True or watch.get("market_identity_verified") is not True:
            raise ValueError("Unverified watchlist manifest")
        by_game[(stamp(watch["game_start_utc"]).astimezone(ET).date(),
                 str(watch["fixture_id"]))].append(stages)
    return by_game


def qualified_trades(data, now):
    tickers = set()
    for (_, fixture), contracts in data.items():
        for stages in contracts:
            entry = stages.get("entry")
            if not entry or entry.get("signal") != "BUY_YES":
                continue
            eligible(entry, now=now)
            ticker = entry["market_ticker"]
            if ticker in tickers or entry["fixture_id"] != fixture:
                raise ValueError("Duplicate or mismatched qualified paper entry")
            tickers.add(ticker)
            entry_day = stamp(entry["observed_utc"]).astimezone(CT).date()
            settlement = stages.get("settlement")
            if settlement is None:
                yield fixture, entry_day, None, None
                continue
            close = stages.get("close")
            eligible(entry, close, settlement, now=now)
            result = settlement.get("winning_team")
            if (settlement.get("paper_only") is not True
                or settlement.get("orders_placed") != 0
                or settlement.get("paper_contracts") != 1
                or result not in ("yes", "no")):
                raise ValueError("Invalid paper settlement")
            entry_price = Decimal(str(entry["ask_dollars"]))
            close_price = Decimal(str(close["ask_dollars"]))
            fee = Decimal(str(entry["scheduled_paper_fee_dollars"]))
            net = Decimal(str(settlement["post_fee_paper_pnl_dollars"]))
            settled = stamp(settlement["official_settled_at_utc"])
            if (not stamp(entry["game_start_utc"]) < settled <= stamp(settlement["observed_utc"])
                or not 0 < close_price < 1
                or fee != Decimal(str(settlement["scheduled_paper_fee_dollars"]))
                or net != (int(result == "yes") - entry_price - fee).quantize(Decimal("0.01"))):
                raise ValueError("Inconsistent settlement evidence")

            yield fixture, entry_day, settled.astimezone(CT).date(), (
                result == "yes", net, entry_price + fee, close_price - entry_price)


def summarize(rows, start, end, scheduled_games):
    settled = [row for row in rows if row[2] is not None and start <= row[2] <= end]
    wins = sum(row[3][0] for row in settled)
    pnl, cost, clv = (sum((row[3][index] for row in settled), Decimal("0"))
                      for index in (1, 2, 3))
    return {"scheduled_slate_games": scheduled_games,
            "settled_slate_games": len({row[0] for row in settled}),
            "settled_contracts": len(settled),
            "trades_placed": sum(start <= placed <= end for _, placed, _, _ in rows),
            "wins": wins, "losses": len(settled) - wins,
            "pending": sum(placed <= end and (day is None or day > end)
                           for _, placed, day, _ in rows),
            "settlement_dates": sorted({row[2].isoformat() for row in settled}),
            "settled_cost": str(cost), "clv_sum": str(clv),
            "post_fee_paper_pnl_dollars": f"{pnl:.2f}"}


def publish_recap(kind, key, data, *, call=api, sender=send):
    if kind not in ("daily", "weekly", "monthly"):
        raise ValueError("Unknown recap")
    revision = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]
    reservation = f"sport=nhl | {key} | {kind}_recap | {revision}"
    issue = reserve(reservation, call=call)
    if issue is None:
        return {"key": reservation, "status": "already_reserved"}
    webhook = os.environ[{"daily":"STATRALLY_NHL_DAILY_RECAP_WEBHOOK",
                          "weekly":"STATRALLY_NHL_WEEKLY_RECAP_WEBHOOK",
                          "monthly":"STATRALLY_NHL_MONTHLY_RECAP_WEBHOOK"}[kind]]
    payout = Decimal(data["post_fee_paper_pnl_dollars"])
    cost = Decimal(data["settled_cost"])
    count = data["settled_contracts"]
    roi = f"{100 * payout / cost:.2f}%" if cost else "N/A"
    clv = f"{100 * Decimal(data['clv_sum']) / count:+.2f} pp" if count else "N/A"
    payload = {"embeds":[{"title":"StatRally NHL PAPER | "+kind.upper()+" | "+key,
        "description":("**Scheduled games:** "+str(data["scheduled_slate_games"])+
        "\\n**Settled games:** "+str(data["settled_slate_games"])+
        "\\n**Settled contracts:** "+str(data["settled_contracts"])+
        "\\n**Post-fee PAPER P&L:** $"+data["post_fee_paper_pnl_dollars"]+
        "\\n**Trades placed** "+str(data["trades_placed"])+
        "\\n**W–L** "+str(data["wins"])+"–"+str(data["losses"])+
        "\\n**Post-fee ROI** "+roi+
        "\\n**Average CLV (closing ask minus entry ask)** "+clv+
        "\\n**Pending** "+str(data["pending"])+
        "\\n**Settlement dates (Central)** "+(", ".join(data["settlement_dates"]) or "N/A")+
        "\\n**Real orders:** 0"),"color":3447003}],
        "allowed_mentions":{"parse":[]}}
    try:
        message_id = sender(webhook, payload)
    except Exception as exc:
        call("POST", PUBLIC, "/issues/"+str(issue)+"/comments",
             {"body":RECEIPT+json.dumps({"state":"AMBIGUOUS_OR_FAILED",
                    "error_type":type(exc).__name__,"manual_review_required":True})})
        return {"key":reservation,"status":"AMBIGUOUS_OR_FAILED"}
    call("POST", PUBLIC, "/issues/"+str(issue)+"/comments",
         {"body":RECEIPT+json.dumps({"state":"CONFIRMED",
                "discord_message_id":message_id,"paper_only":True})})
    return {"key":reservation,"status":"CONFIRMED"}


def run(*, now=None, schedule=official_slate, source=ledger, call=api, sender=send):
    now = now or datetime.now(timezone.utc)
    end = now.astimezone(CT).date() - timedelta(days=1)
    if end < FIRST_RECAP:
        return []
    rows = list(qualified_trades(source(), now))
    first = max(FIRST_RECAP, end - timedelta(days=6))
    periods = []
    for offset in range((end - first).days + 1):
        day = first + timedelta(days=offset)
        periods.append(("daily", day, day))
        if day.weekday() == 5:
            periods.append(("weekly", day - timedelta(days=6), day))
        if (day + timedelta(days=1)).day == 1:
            periods.append(("monthly", day.replace(day=1), day))
    output = []
    schedule_counts = {}
    for kind, start, finish in periods:
        days = (start + timedelta(days=offset) for offset in range((finish - start).days + 1))
        scheduled = 0
        for day in days:
            if day not in schedule_counts:
                schedule_counts[day] = len(schedule(day))
            scheduled += schedule_counts[day]
        data = summarize(rows, start, finish, scheduled)
        if scheduled or data["trades_placed"] or data["settled_contracts"]:
            key = finish.isoformat() if kind == "daily" else f"{start.isoformat()}_{finish.isoformat()}"
            output.append(publish_recap(kind, key, data, call=call, sender=sender))
    return output


if __name__ == "__main__":
    if os.environ.get("STATRALLY_NHL_PAPER_ONLY") != "true":
        raise ValueError("Paper-only gate required")
    print(json.dumps({"paper_only":True,"orders_placed":0,"recaps":run()}))
