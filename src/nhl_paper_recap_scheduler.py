"""Preview verified NHL paper trade summaries for each official slate."""
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


def completed(day, *, schedule=official_slate, source=ledger):
    scheduled = schedule(day)
    if not scheduled:
        return None
    data = source()
    tickers = set()
    games = set()
    dates = set()
    placed = pending = wins = losses = 0
    pnl = cost = clv = Decimal("0")
    for fixture in scheduled:
        for stages in data.get((day, fixture), []):
            entry = stages.get("entry")
            if not entry or entry.get("signal") != "BUY_YES":
                continue
            eligible(entry)
            ticker = entry["market_ticker"]
            if ticker in tickers or entry["fixture_id"] != fixture:
                raise ValueError("Duplicate or mismatched qualified paper entry")
            tickers.add(ticker)
            placed += 1
            settlement = stages.get("settlement")
            if settlement is None:
                pending += 1
                continue
            close = stages.get("close")
            eligible(entry, close, settlement)
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
            dates.add(settled.astimezone(ZoneInfo("America/Chicago")).date().isoformat())
            games.add(fixture)
            wins += result == "yes"
            losses += result == "no"
            pnl += net
            cost += entry_price + fee
            clv += close_price - entry_price
    return {"slate_date": day.isoformat(), "scheduled_slate_games": len(scheduled),
            "settled_slate_games": len(games), "settled_contracts": wins + losses,
            "trades_placed": placed, "wins": wins, "losses": losses, "pending": pending,
            "settlement_dates": sorted(dates), "settled_cost": str(cost), "clv_sum": str(clv),
            "post_fee_paper_pnl_dollars": f"{pnl:.2f}", "paper_only": True,
            "orders_placed": 0}


def publish_recap(kind, key, data, *, call=api, sender=send):
    if kind not in ("daily", "weekly", "monthly"):
        raise ValueError("Unknown recap")
    reservation = "sport=nhl | " + key + " | " + kind + "_recap"
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


def run(*, now=None, schedule=official_slate, source=ledger,
        call=api, sender=send):
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(ET).date()
    # Only consider completed calendar dates for quiet-slate reporting.
    days = [today-timedelta(days=i) for i in range(1, 2)]
    finished = {}
    output = []
    for day in days:
        value = completed(day, schedule=schedule, source=source)
        if value is None:
            continue
        finished[day] = value
        output.append(publish_recap("daily", day.isoformat(), value,
                                    call=call, sender=sender))
    # Only publish a weekly or monthly report after the entire period ends.
    # Require all scheduled slates, including zero-game dates, to be checked.
    for kind in ("weekly", "monthly"):
        end = today-timedelta(days=1)
        if kind == "weekly":
            end -= timedelta(days=(end.weekday()+2)%7)
            start = end-timedelta(days=6)
        else:
            end = today.replace(day=1)-timedelta(days=1)
            start = end.replace(day=1)
        period = [start+timedelta(days=i) for i in range((end-start).days+1)]
        values = []
        for day in period:
            scheduled = schedule(day)
            if not scheduled:
                continue
            item = finished.get(day) or completed(day, schedule=schedule, source=source)
            if item is None:
                break
            values.append(item)
        else:
            if values:
                aggregate = {"scheduled_slate_games":sum(v["scheduled_slate_games"] for v in values),
                             "settled_slate_games":sum(v["settled_slate_games"] for v in values),
                             "settled_contracts":sum(v["settled_contracts"] for v in values),
                             "post_fee_paper_pnl_dollars":str(sum(
                                 (Decimal(v["post_fee_paper_pnl_dollars"]) for v in values),
                                 Decimal("0")).quantize(Decimal("0.01")))}
                for field in ("trades_placed", "wins", "losses", "pending"):
                    aggregate[field] = sum(v[field] for v in values)
                for field in ("settled_cost", "clv_sum"):
                    aggregate[field] = str(sum(Decimal(v[field]) for v in values))
                aggregate["settlement_dates"] = sorted({
                    day for value in values for day in value["settlement_dates"]})
                output.append(publish_recap(kind, start.isoformat()+"_"+end.isoformat(),
                                            aggregate, call=call, sender=sender))
    return output


if __name__ == "__main__":
    if os.environ.get("STATRALLY_NHL_PAPER_ONLY") != "true":
        raise ValueError("Paper-only gate required")
    print(json.dumps({"paper_only":True,"orders_placed":0,"recaps":run()}))
