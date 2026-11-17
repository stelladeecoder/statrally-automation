"""Publish verified zero-order NFL ATD paper decisions and closed-date recaps."""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from nhl_moneyline_ledger_delivery import PUBLIC, RECEIPT, api, reserve, send, stamp
from nhl_paper_recap_scheduler import summarize

CENTRAL = ZoneInfo("America/Chicago")
SETTLEMENT_RETENTION_DAYS = 45
TICKER = re.compile(r"KXNFLANYTD-[A-Z0-9-]+")
PLAYER = re.compile(r"00-[0-9]{7}")
FIXTURE = re.compile(r"20[0-9]{2}w[0-9]{1,2}-[A-Z]{2,3}-[A-Z]{2,3}")


def require_paper(row):
    if (row.get("paper_only") is not True or type(row.get("orders_placed")) is not int
        or row["orders_placed"] != 0):
        raise ValueError("Invalid NFL paper-only evidence")


def trade_key(row, ticker_key):
    key = row["fixture_id"], row["player_id"], row[ticker_key]
    if not all(pattern.fullmatch(value) for pattern, value in zip((FIXTURE, PLAYER, TICKER), key)):
        raise ValueError("Invalid NFL trade identity")
    return key


def decisions(reports, now):
    entries = {}
    for report in reports:
        require_paper(report)
        if report.get("schema") != "nfl-atd-paper-decisions-v1":
            raise ValueError("Unexpected NFL decision schema")
        for row in report["records"]:
            if row.get("signal") != "BUY_YES":
                continue
            require_paper(row)
            if row.get("sport") != "nfl" or row.get("market_type") != "atd":
                raise ValueError("Unexpected market type")
            key = trade_key(row, "market_ticker")
            observed, kickoff = stamp(row["observed_utc"]), stamp(row["kickoff_utc"])
            price, p, fee, edge = (Decimal(str(row[k])) for k in
                ("ask_dollars", "model_probability", "scheduled_paper_fee_dollars", "post_fee_edge"))
            if (not all(value.is_finite() for value in (price, p, fee, edge))
                or not (0 < price < 1 and 0 < p < 1 and fee >= 0 and edge > 0)
                or abs(edge - (p-price-fee)) > Decimal("0.00000000000000000000000001")
                or not timedelta(minutes=75) <= kickoff-observed <= timedelta(minutes=90)
                or observed > now
                or not all(re.fullmatch(r"[0-9a-f]{64}", row[field])
                           for field in ("model_sha256", "orderbook_sha256"))):
                raise ValueError("NFL BUY_YES lacks verified edge or pregame evidence")
            # Earliest qualified observation is the immutable source for this trade key.
            old = entries.get(key)
            if old is None or observed < stamp(old["observed_utc"]):
                entries[key] = row
            elif observed == stamp(old["observed_utc"]) and row != old:
                raise ValueError("Conflicting NFL entry receipts")
    return entries


def settle_rows(entries, reports, now):
    settled = {}
    for report in reports:
        require_paper(report)
        for row in report["records"]:
            if row.get("schema") != "nfl-atd-paper-settlement-v1":
                continue
            require_paper(row)
            if row.get("sport") != "nfl" or row.get("market_type") != "atd":
                raise ValueError("Unexpected settlement market type")
            key = trade_key(row, "ticker")
            if key not in entries:
                continue
            entry = entries[key]
            timestamp = stamp(row["settled_at_utc"])
            cost, pnl, clv = (Decimal(str(row[field])) for field in
                ("entry_cost_dollars", "post_fee_paper_pnl_dollars", "closing_line_value_dollars"))
            price = Decimal(str(entry["ask_dollars"]))
            won = row["settlement_result"] == "yes"
            if (not all(value.is_finite() for value in (cost, pnl, clv))
                or not stamp(entry["kickoff_utc"]) < timestamp <= now
                or row["settlement_result"] not in ("yes", "no")
                or cost != price + Decimal(str(entry["scheduled_paper_fee_dollars"]))
                or pnl != int(won) - cost or not 0 < price + clv < 1):
                raise ValueError("Conflicting NFL settlement math or timestamps")
            result = timestamp.astimezone(CENTRAL).date(), (won, pnl, cost, clv)
            if key in settled and settled[key] != result:
                raise ValueError("Conflicting settlement receipts")
            settled[key] = result
    return [(key[0], stamp(row["observed_utc"]).astimezone(CENTRAL).date(),
             *settled.get(key, (None, None))) for key, row in entries.items()]


def periods(now):
    last_closed = now.astimezone(CENTRAL).date() - timedelta(days=1)
    for offset in range(6, -1, -1):
        day = last_closed - timedelta(days=offset)
        yield "daily", day, day
        if day.weekday() == 5:
            yield "weekly", day - timedelta(days=6), day
        if (day + timedelta(days=1)).day == 1:
            yield "monthly", day.replace(day=1), day


def deliver(key, hook, title, body, *, call=api, sender=send):
    webhook = os.environ[hook]
    if not webhook.startswith("https://discord.com/api/webhooks/"):
        raise ValueError("Missing or invalid dedicated NFL webhook")
    issue = reserve(key, call=call, title_prefix="NFL ATD PAPER Discord | ")
    if issue is None:
        return None
    receipt = sender(webhook, {"embeds":[{"title":title,"description":body,"color":3447003}],
                               "allowed_mentions":{"parse":[]}})
    if not isinstance(receipt, str) or not re.fullmatch(r"[0-9]+", receipt):
        raise ValueError("No verified Discord message ID")
    call("POST", PUBLIC, f"/issues/{issue}/comments", {"body":RECEIPT+json.dumps({
        "state":"CONFIRMED","discord_message_id":receipt,"orders_placed":0,"paper_only":True})})
    print(f"NFL Discord message ID {receipt}")
    return receipt


def run_picks(entries, now, *, publish=deliver):
    for key, row in sorted(entries.items()):
        if not now < stamp(row["kickoff_utc"]):
            continue
        publish("pick | " + " | ".join(key), "STATRALLY_NFL_PICKS_WEBHOOK",
                "[PAPER TRADE] NFL ATD | Kalshi",
                f"{key[0]} | {key[1]}\n{key[2]}\n"
                f"BUY YES at ${row['ask_dollars']} | Probability {Decimal(row['model_probability']):.2%}\n"
                f"Fee ${row['scheduled_paper_fee_dollars']} | Post-fee edge {Decimal(row['post_fee_edge']):.2%}\n"
                "$0 real orders")


def retained_history_start(now):
    """Exclude the oldest Central date when retention may cover only part of it."""
    return now.astimezone(CENTRAL).date() - timedelta(days=SETTLEMENT_RETENTION_DAYS - 1)


def run_recaps(rows, now, *, publish=deliver, history_start=None):
    for kind, start, end in periods(now):
        if history_start is not None and start < history_start:
            print(f"Deferred NFL {kind} recap | complete settlement history unavailable for {start} through {end}")
            continue
        data = summarize(rows, start, end, 0)
        if not (data["trades_placed"] or data["settled_contracts"] or data["pending"]):
            continue
        cost = Decimal(data["settled_cost"])
        count = data["settled_contracts"]
        pnl = Decimal(data["post_fee_paper_pnl_dollars"])
        roi = f"{pnl / cost:.2%}" if cost else "N/A"
        clv = f"{Decimal(data['clv_sum']) / count:+.2%}" if count else "N/A"
        revision = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]
        publish(f"{kind} | {start} | {end} | {revision}", "STATRALLY_NFL_RESULTS_WEBHOOK",
                f"[PAPER RECAP] NFL ATD | {kind.title()} | {end}",
                f"Central period {start} through {end}\n"
                f"Settlement dates {', '.join(data['settlement_dates']) or 'N/A'}\n"
                f"W–L {data['wins']}–{data['losses']} | Pending {data['pending']}\n"
                f"Post-fee P&L ${pnl:.2f} | ROI {roi} | Avg. CLV {clv}\n$0 real orders")


def main(mode, directory):
    if os.environ.get("STATRALLY_NFL_PAPER_ONLY") != "true":
        raise ValueError("NFL paper-only workflow required")
    root = Path(directory)
    now = datetime.now(timezone.utc)
    entries = decisions([json.loads(p.read_text()) for p in
                         sorted(root.glob("*/nfl_atd_paper_decisions.json"))], now)
    if mode == "picks":
        run_picks(entries, now)
    elif mode == "recaps":
        results = [json.loads(p.read_text()) for p in sorted(root.glob("*/nfl_atd_settlements.json"))]
        history_start = retained_history_start(now)
        rows = settle_rows(entries, results, now)
        # An older entry with no surviving settlement is ambiguous. Avoid
        # counting an expired result as a pending trade.
        if any(placed < history_start and settled is None for _, placed, settled, _ in rows):
            raise ValueError("NFL recap requires durable settlement history for older decisions")
        run_recaps(rows, now, history_start=history_start)
    else:
        raise ValueError("Unknown NFL delivery mode")


if __name__ == "__main__":
    main(*sys.argv[1:])
