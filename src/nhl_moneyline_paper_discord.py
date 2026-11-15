"""NHL moneyline paper-only Discord payloads; never connects to Kalshi or places orders.

Consumes a private validated report handoff only. No network calls at import.
The existing NHL Even/Odd channel publishers are intentionally untouched.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

CHANNEL_SECRETS = {
    "watchlist": "STATRALLY_NHL_WATCHLIST_WEBHOOK",
    "picks": "STATRALLY_NHL_PICKS_WEBHOOK",
    "results": "STATRALLY_NHL_RESULTS_WEBHOOK",
}
BANDS = {"underdog": "Underdog <50¢", "short_favorite": "Short favorite 50–59¢",
         "heavy_favorite": "Heavy favorite 60¢+"}
THRESHOLDS = ("0.025", "0.035", "0.05")
MAX_ROWS = 100
MAX_DESC = 3500


def _decimal(value):
    if value is None:
        return None
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("Nonfinite quote or probability")
    return number


def _time(value):
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return d.astimezone(timezone.utc)


def validate(report, stage, *, now=None):
    """Fail closed: producer must attest snapshots, fee, identities, and paper mode."""
    now = now or datetime.now(timezone.utc)
    if stage not in CHANNEL_SECRETS:
        raise ValueError("Unknown NHL moneyline route")
    if (report.get("schema_version") != "nhl-kalshi-moneyline-paper-v1"
        or report.get("market_series") != "KXNHLGAME"
        or report.get("paper_trade") is not True
        or report.get("orders_placed") != 0
        or report.get("run_mode") != "verified_prospective"
        or report.get("stage") != stage
        or report.get("source_repository") != "stelladeecoder/statrally-even-odd-models"):
        raise ValueError("Unverified NHL Kalshi paper handoff")
    emitted = _time(report["generated_at_utc"])
    if emitted > now or (now - emitted).total_seconds() > 3600:
        raise ValueError("Stale or future NHL report")
    rows = report.get("games")
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("Invalid game records")
    seen = set()
    for row in rows:
        identifier = row.get("game_id")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
            raise ValueError("Duplicate or missing game identity")
        seen.add(identifier)
        if not row.get("fixture_verified") or not row.get("market_identity_verified"):
            raise ValueError("Unverified NHL fixture or market")
        if not isinstance(row.get("fixture"), str) or not row.get("fixture").strip():
            raise ValueError("Fixture label missing")
        if not isinstance(row.get("market_ticker"), str) or not row["market_ticker"].startswith("KXNHLGAME-"):
            raise ValueError("Wrong Kalshi market")
        if not isinstance(row.get("selected_team"), str) or not row["selected_team"]:
            raise ValueError("Contract team unspecified")
        p = _decimal(row.get("model_probability"))
        if p is None or not 0 <= p <= 1:
            raise ValueError("Invalid model probability")
        if stage != "results":
            _time(row["entry_observed_utc"])
            before = _decimal(row.get("minutes_before_start"))
            measured = (_time(row["game_start_utc"]) - _time(row["entry_observed_utc"])).total_seconds() / 60
            if (before is None or not 45 <= before <= 60 or
                not 45 <= measured <= 60 or abs(Decimal(str(measured)) - before) > Decimal("0.1")):
                raise ValueError("Actual entry snapshot must be 45-60 minutes pre-puck")
            if row.get("status") not in ("PAPER_TRADE", "NO_BET"):
                raise ValueError("Missing paper signal status")
            if row["status"] == "PAPER_TRADE":
                if (row.get("fee_verified") is not True
                    or row.get("ask_dollars") is None
                    or row.get("net_ev_on_cost") is None
                    or row.get("depth_contracts") is None):
                    raise ValueError("Paper signal missing verified executable evidence")
                ev = _decimal(row["net_ev_on_cost"])
                selected = [t for t in THRESHOLDS if ev >= Decimal(t)]
                if not selected:
                    raise ValueError("Nonqualifying paper signal")
                if row.get("band") not in BANDS or _decimal(row["depth_contracts"]) < 1:
                    raise ValueError("Bad size or band")
        else:
            if row.get("status") not in ("SETTLED", "PENDING", "MISSING"):
                raise ValueError("Invalid settlement state")
            if row["status"] == "SETTLED":
                if (row.get("settlement_verified") is not True
                    or row.get("paper_profit_dollars") is None
                    or row.get("closing_observed_utc") is None):
                    raise ValueError("Unverified paper settlement or closing time")
                _time(row["closing_observed_utc"])
    return rows


BLUE = 0x3498DB
TEAL = 0x1ABC9C
GREEN = 0x2ECC71
RED = 0xE74C3C
NEUTRAL = 0x95A5A6


def _money(value):
    d = _decimal(value)
    return "Unavailable" if d is None else f"USD {d:.2f}"


def _tier(row):
    ask = _decimal(row.get("ask_dollars"))
    if ask is None:
        return "Unknown (no executable ask)"
    if not 0 < ask < 1:
        raise ValueError("Invalid selected-side executable ask")
    if ask < Decimal(".50"):
        code = "underdog"
    elif ask < Decimal(".60"):
        code = "short_favorite"
    else:
        code = "heavy_favorite"
    if row.get("status") == "PAPER_TRADE" and row.get("band") != code:
        raise ValueError("Paper signal tier does not match its executable ask")
    return BANDS[code]


def _card(title, description, color, *, footer=None, fields=None):
    if len(description) > MAX_DESC:
        raise ValueError("Oversize mobile Discord card")
    embed = {"title": title, "description": description, "color": color,
             "footer": {"text": footer or
                        "StatRally · NHL Moneyline · [PAPER TRADE] research only · No real orders"}}
    if fields:
        embed["fields"] = fields
    return {"embeds": [embed], "allowed_mentions": {"parse": []}}


def _validate_moneyline_evidence(row, stage):
    p = _decimal(row.get("model_probability"))
    if p is None or not Decimal("0") <= p <= Decimal("1"):
        raise ValueError("Invalid model probability")
    ask = _decimal(row.get("ask_dollars"))
    fee = _decimal(row.get("fee_dollars"))
    ev = _decimal(row.get("net_ev_on_cost"))
    depth = _decimal(row.get("depth_contracts"))
    if ask is not None and not Decimal("0") < ask < Decimal("1"):
        raise ValueError("Quote out of contract bounds")
    if fee is not None and fee < 0:
        raise ValueError("Negative market fee")
    if depth is not None and depth < 0:
        raise ValueError("Negative book depth")
    if stage == "picks" and row["status"] != "PAPER_TRADE":
        return
    if row["status"] == "PAPER_TRADE":
        if (row.get("fee_verified") is not True or
            ask is None or fee is None or ev is None or
            depth is None or depth < 1):
            raise ValueError("Paper signal missing verified price/fee/EV/depth")
        if abs(ev - (p / (ask + fee) - Decimal("1"))) > Decimal(".005"):
            raise ValueError("Net EV inconsistent with model probability and all-in price")
        if ev < Decimal(THRESHOLDS[0]):
            raise ValueError("Below the first paper EV threshold")
        _tier(row)
    elif row.get("fee_verified") is not True and ev is not None:
        # NO BET may contain an unverified tentative price but never show computed EV.
        raise ValueError("No EV figures from unverified fees")
    if stage == "results" and row["status"] == "SETTLED":
        if type(row.get("paper_win")) is not bool:
            raise ValueError("Settled result requires a verified WIN/LOSS bool")
        if (row.get("settlement_verified") is not True or
            row.get("fee_verified") is not True or
            ask is None or fee is None or
            row.get("closing_ask_dollars") is None or
            row.get("paper_profit_dollars") is None):
            raise ValueError("Incomplete verified paper outcome")


def _pregame_text(row):
    fixture = row["fixture"]
    p = _decimal(row["model_probability"])
    fee_ok = row.get("fee_verified") is True
    fee = _decimal(row.get("fee_dollars")) if fee_ok else None
    ev = _decimal(row.get("net_ev_on_cost")) if fee_ok else None
    depth = _decimal(row.get("depth_contracts"))
    status = row["status"]
    text = [
        f"**{fixture}**",
        f"**{row['selected_team']} to WIN** · Kalshi YES",
        f"**Model Win Prob:** {p:.1%}",
        f"**Kalshi Executable Ask:** {_money(row.get('ask_dollars'))}",
        f"**Fee:** {_money(fee)}" if fee_ok else "**Fee:** Unverified",
        f"**Orderbook Depth:** {depth:g} contracts" if depth is not None else
            "**Orderbook Depth:** Unavailable",
        f"**Net EV (post-fee):** {ev:+.2%}" if ev is not None else
            "**Net EV (post-fee):** UNKNOWN",
        f"**Odds Tier:** {_tier(row)}",
    ]
    if status == "PAPER_TRADE":
        passed = ["+" + str(Decimal(t)*100) + "%" for t in THRESHOLDS
                  if ev is not None and ev >= Decimal(t)]
        text.append("**[PAPER TRADE] QUALIFIED** · " + " / ".join(passed))
    else:
        text.append("**NO BET** · Not qualified or insufficient verified market evidence")
    return "\n".join(text)


def _outcome_text(row):
    status = row["status"]
    lines = [f"**{row['fixture']}**",
             f"**Selected team:** {row['selected_team']} · Kalshi YES",
             f"**Model Win Prob:** {_decimal(row['model_probability']):.1%}"]
    if status != "SETTLED":
        lines.extend([f"**Status:** {status}",
                      "**Entry / Closing CLV:** Pending verified settlement and snapshots",
                      "**Post-Fee Paper P&L:** Pending"])
        return "\n".join(lines)
    entry = _decimal(row["ask_dollars"])
    closing = _decimal(row["closing_ask_dollars"])
    if not 0 < closing < 1:
        raise ValueError("Invalid closing executable ask")
    entry_at = _time(row["entry_observed_utc"])
    closing_at = _time(row["closing_observed_utc"])
    start = _time(row["game_start_utc"])
    if not (45 <= (start-entry_at).total_seconds()/60 <= 60 and
            0 <= (start-closing_at).total_seconds()/60 <= 5 and
            entry_at < closing_at):
        raise ValueError("Entry and close observations are not within verified windows")
    move = closing-entry
    if row.get("ask_price_move_dollars") is not None and abs(
            _decimal(row["ask_price_move_dollars"])-move) > Decimal(".0001"):
        raise ValueError("Stored close movement conflicts with quote pair")
    contracts = _decimal(row.get("paper_contracts", 1))
    if (contracts is None or contracts <= 0 or contracts != contracts.to_integral_value()):
        raise ValueError("Invalid paper contract count")
    actual_profit = _decimal(row["paper_profit_dollars"])
    expected_profit = (Decimal("1") if row["paper_win"] else Decimal("0")) * contracts - entry * contracts - _decimal(row["fee_dollars"])
    if abs(actual_profit - expected_profit) > Decimal(".01"):
        raise ValueError("Post-fee paper P&L inconsistent with YES settlement, entry and fees")
    lines.extend([
        f"**Result:** {'WIN' if row['paper_win'] else 'LOSS'}",
        f"**Entry Ask:** {_money(entry)} · **Puck-Drop Closing Ask:** {_money(closing)}",
        f"**CLV Proxy (ask movement):** {move:+.3f} USD",
        "**CLV Note:** Quote-to-quote movement only, not an executed fill",
        f"**Entry Fee:** {_money(row.get('fee_dollars'))} · {contracts:g} paper contract(s)",
        f"**Post-Fee Paper P&L:** {_money(row['paper_profit_dollars'])}",
    ])
    return "\n".join(lines)


def _scorecard(report):
    totals = report.get("cumulative", {})
    n = totals.get("settled_paper_games")
    if type(n) is not int or n < 0:
        raise ValueError("Verified cumulative paper game count required")
    roi = _decimal(totals.get("net_paper_roi"))
    if roi is not None and (roi < Decimal("-1") or not roi.is_finite()):
        raise ValueError("Bad cumulative paper ROI")
    wins = totals.get("wins")
    losses = totals.get("losses")
    if any(type(x) is not int or x < 0 for x in (wins, losses)
           if x is not None):
        raise ValueError("Bad cumulative win/loss totals")
    if wins is not None and losses is not None and wins+losses != n:
        raise ValueError("Scorecard wins/losses differ from completed paper sample")
    body = [f"**Completed [PAPER TRADE] Games:** {n}",
            f"**Validation Progress:** {n}/150 minimum · {n}/250 extended",
            f"**Post-Fee Paper ROI:** {roi:+.2%}" if roi is not None else
                "**Post-Fee Paper ROI:** Pending verified capital and settlement",
            "**Real Orders:** 0 · Disabled"]
    if wins is not None and losses is not None:
        body.insert(1, f"**Record:** {wins} WIN / {losses} LOSS")
    return _card("📊 NHL MONEYLINE | PAPER SCORECARD",
                 "\n".join(body), BLUE,
                 footer="StatRally · Prospective paper sample only · 150–250 games for review")


def render(report, stage, *, now=None):
    rows = validate(report, stage, now=now)
    if stage == "picks":
        rows = [r for r in rows if r["status"] == "PAPER_TRADE"]
    for row in rows:
        _validate_moneyline_evidence(row, stage)
    cards = []
    if stage in ("watchlist", "picks"):
        title = ("🏒 NHL | DAILY MONEYLINE WATCHLIST [PAPER]"
                 if stage == "watchlist" else
                 "🏒 NHL | MONEYLINE PICKS [PAPER TRADE]")
        color = BLUE if stage == "watchlist" else TEAL
        if not rows:
            return [_card(title, "No qualified paper trades in this slate.",
                          color)]
        for index, row in enumerate(rows, 1):
            cards.append(_card(f"{title} · {index}/{len(rows)}",
                               _pregame_text(row), color))
        return cards
    # Results: retain the WIN / LOSS per-game cards, then append a scorecard.
    for row in rows:
        outcome = row["status"] == "SETTLED"
        won = row.get("paper_win") is True if outcome else False
        color = (GREEN if won else RED) if outcome else NEUTRAL
        header = ("🟩 WIN" if won else "🟥 LOSS") if outcome else "⏳ PENDING"
        cards.append(_card(f"{header} · 🏒 NHL MONEYLINE [PAPER TRADE]",
                           _outcome_text(row), color))
    cards.append(_scorecard(report))
    return cards


def route(stage, environ):
    if stage not in CHANNEL_SECRETS:
        raise ValueError("Unknown stage")
    values = {key: environ.get(secret, "").strip()
              for key, secret in CHANNEL_SECRETS.items()}
    present = [v for v in values.values() if v]
    if len(present) != len(set(present)):
        raise ValueError("Duplicate NHL channel webhooks: refusing misrouting")
    return values[stage]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--stage", choices=tuple(CHANNEL_SECRETS), required=True)
    args = parser.parse_args()
    report = json.loads(Path(args.input).read_text(encoding="utf-8"))
    payloads = render(report, args.stage)
    # Deliberately preview-only until the private producer, persistent receipts,
    # fee-aware quotes and real two-snapshot lifecycle are verified end to end.
    print(json.dumps({"stage": args.stage, "webhook_secret": CHANNEL_SECRETS[args.stage],
                      "payloads": payloads, "delivery_enabled": False},
                     sort_keys=True))


if __name__ == "__main__":
    main()
