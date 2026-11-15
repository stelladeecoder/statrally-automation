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
            if before is None or not 45 <= before <= 60:
                raise ValueError("Watchlist/picks must be 45-60 minutes pre-puck")
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


def _format(row, stage):
    name = row["fixture"].replace("@", "at")
    team = row["selected_team"]
    p = _decimal(row["model_probability"])
    lines = [f"**{name}** · {team} YES · Model {p:.1%}"]
    if stage != "results":
        ask = _decimal(row.get("ask_dollars"))
        fee = _decimal(row.get("fee_dollars"))
        ev = _decimal(row.get("net_ev_on_cost"))
        depth = _decimal(row.get("depth_contracts"))
        quote = ("Ask unavailable" if ask is None else f"Ask {ask:.2f} USD")
        quote += (" · Fee unverified" if fee is None else f" · Fee ${fee:.2f}")
        quote += (" · Depth unavailable" if depth is None else f" · Depth {depth} contracts")
        lines.append(quote)
        lines.append("Net EV UNKNOWN" if ev is None else f"Net EV {ev:+.2%}")
        if row["status"] == "PAPER_TRADE":
            tags = " / ".join("+" + str(Decimal(t) * 100) + "%" for t in THRESHOLDS if ev >= Decimal(t))
            lines.append(f"**PAPER TRADE** · {BANDS[row['band']]} · Thresholds {tags}")
        else:
            lines.append("**NO BET** · Not qualified / insufficient verified market data")
    else:
        lines.append(f"Settlement: **{row['status']}**")
        close = _decimal(row.get("closing_ask_dollars"))
        lines.append("Closing ask: " + ("missing" if close is None else f"${close:.2f}"))
        move = _decimal(row.get("ask_price_move_dollars"))
        lines.append("Entry-to-close ask movement: " + ("unavailable" if move is None else f"${move:+.3f} (proxy, not executed CLV)"))
        profit = _decimal(row.get("paper_profit_dollars"))
        lines.append("Post-fee paper P&L: " + ("pending" if profit is None else f"${profit:+.2f}"))
    return "\n".join(lines)


def render(report, stage, *, now=None):
    rows = validate(report, stage, now=now)
    if stage == "picks":
        rows = [r for r in rows if r["status"] == "PAPER_TRADE"]
    heading = {"watchlist": "NHL MONEYLINE | FULL PAPER WATCHLIST",
               "picks": "NHL MONEYLINE | QUALIFIED PAPER SIGNALS",
               "results": "NHL MONEYLINE | PAPER RESULTS"}[stage]
    chunks = []
    part = []
    for record in rows:
        line = _format(record, stage)
        if len(line) > MAX_DESC:
            raise ValueError("Oversize NHL description")
        if part and len("\n\n".join(part + [line])) > MAX_DESC:
            chunks.append("\n\n".join(part))
            part = []
        part.append(line)
    if part:
        chunks.append("\n\n".join(part))
    if not chunks:
        chunks = ["No qualified paper signals." if stage == "picks" else "No validated games in this report."]
    if len(chunks) > 10:
        raise ValueError("Too many Discord embeds")
    if stage == "results":
        totals = report.get("cumulative", {})
        if not (isinstance(totals.get("settled_paper_games"), int)
                and totals["settled_paper_games"] >= 0):
            raise ValueError("Missing verified cumulative sample count")
        net = _decimal(totals.get("net_paper_roi"))
        chunks[0] += f"\n\n**Running sample:** {totals['settled_paper_games']} settled paper games"
        chunks[0] += (" · ROI pending" if net is None else f" · Net paper ROI {net:+.2%}")
    return [{"embeds": [{"title": heading + (f" ({i}/{len(chunks)})" if len(chunks) > 1 else ""),
                         "description": chunk,
                         "color": {"watchlist": 0x3498db, "picks": 0x3498db, "results": 0x95a5a6}[stage],
                         "footer": {"text": "StatRally research · PAPER ONLY · No real orders or verified fills"}}],
             "allowed_mentions": {"parse": []}} for i, chunk in enumerate(chunks, 1)]


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
