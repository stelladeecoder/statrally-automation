"""NHL paper recap aggregation using verified private ledger events only.

No zero-game or partial-slate Discord messages. ET game date never changes
when settlement arrives after midnight. Read-only aggregation.
"""
from collections import defaultdict
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from datetime import datetime
from nhl_moneyline_ledger_delivery import pages, records, PRIVATE, api, stamp
from decimal import Decimal

ET = ZoneInfo("America/New_York")


def recap_candidates(*, now=None, call=api):
    now = now or datetime.now(ET)
    by_day = defaultdict(list)
    for issue in pages(PRIVATE, "/issues?state=all", call=call):
        if not str(issue.get("title", "")).startswith("StatRally NHL Moneyline PAPER | "):
            continue
        stages = records(issue, call=call)
        if not stages or "watchlist" not in stages:
            continue
        w = stages["watchlist"]
        day = stamp(w["game_start_utc"]).astimezone(ET).date()
        by_day[day].append(stages)
    daily = {}
    for day, contracts in by_day.items():
        if not contracts or any("settlement" not in s for s in contracts):
            continue
        if any(s["settlement"].get("settlement_verified") is not True or
               s["settlement"].get("post_fee_paper_pnl_dollars") is None
               for s in contracts):
            continue
        daily[day] = contracts
    # The private watchlist is a manifest of observed eligible contracts,
    # NOT authoritative proof of all scheduled games. Do not publish final
    # daily/weekly/monthly recaps until a verified complete slate manifest exists.
    return {"verified_contract_days": len(daily), "ready_to_publish": [],
            "reason": "complete_scheduled_slate_manifest_not_verified",
            "paper_only": True, "orders_placed": 0}


if __name__ == "__main__":
    import json
    print(json.dumps(recap_candidates(), default=str))
