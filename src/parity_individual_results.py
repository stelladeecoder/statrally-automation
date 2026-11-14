"""Individual verified Even/Odd results and labeled Discord route tests."""
import argparse
import os
from datetime import datetime, timedelta, timezone

from m13_discord_embeds import WATCHLIST_FLAGS, COMPETITIONS
from parity_recaps import CENTRAL, collect, deliver, history
from parity_research import LEAGUES

HOOKS = {"soccer": "SOCCER_RESULTS_HOOK", "hockey": "NHL_RESULTS_HOOK"}


def card(item, *, test=False):
    forecast, outcome = item["forecast"], item["outcome"]
    side = forecast["prediction"]
    actual = outcome["actual"]
    win = side == actual
    sport = item["sport"]
    league = forecast["league"]
    competition = "🏒 NHL"
    if sport == "soccer":
        name = COMPETITIONS.get(league.removeprefix("soccer_"), LEAGUES[league][2])
        flag = WATCHLIST_FLAGS.get(name.removeprefix("UEFA "), "⚽")
        competition = f"{flag} {name}"
    lines = [f"**{forecast['away']} @ {forecast['home']}**"]
    home, away = outcome.get("home_score"), outcome.get("away_score")
    if home is not None and away is not None:
        lines.append(f"Final · {forecast['away']} **{away}–{home}** {forecast['home']}")
    lines.append(f"**Pick {side}** · **Result {actual}** · {outcome['total']} total goals")
    marker = "⭐ " if item["starred"] else ""
    lines.append(f"Pregame model estimate · {marker}{forecast['p_' + side.lower()]:.1%}")
    if item["starred"]:
        lines.extend(["", "⭐ 🟨 **VERY HIGH MODEL PROBABILITY · 70%+**"
                      " · descriptive only, not validated reliability"])
    label = "🟩 WIN" if win else "🟥 LOSS"
    if test:
        label = f"TEST POST · {label}"
        lines.insert(0, "*Sample score and prediction for delivery verification.*")
    return {"embeds": [{"title": f"{label} · {competition}",
                        "description": "\n".join(lines),
                        "color": 0x2ECC71 if win else 0xE74C3C}],
            "allowed_mentions": {"parse": []}}


def example(sport):
    soccer = sport == "soccer"
    return {
        "sport": sport, "starred": not soccer,
        "forecast": {"league": "soccer_brasileirao" if soccer else "nhl",
                     "away": "Atlético-MG" if soccer else "Colorado Avalanche",
                     "home": "Mirassol" if soccer else "Montreal Canadiens",
                     "prediction": "ODD", "p_odd": .527 if soccer else .726},
        "outcome": {"actual": "ODD" if soccer else "EVEN", "total": 3 if soccer else 6,
                    "away_score": 1 if soccer else 2, "home_score": 2 if soccer else 4},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    repo = os.environ["GITHUB_REPOSITORY"]
    hooks = {sport: os.environ.get(name, "") for sport, name in HOOKS.items()}
    if hooks["soccer"] and hooks["soccer"] == hooks["hockey"]:
        raise ValueError("Results channels require distinct destinations")
    issues = [item for item in history(repo, "/issues?state=all") if "pull_request" not in item]
    if args.test:
        rows = [example(sport) for sport in hooks]
    else:
        now = datetime.now(timezone.utc)
        day = now.astimezone(CENTRAL).date()
        rows = collect(repo, issues, day - timedelta(days=7), day, now)
    failures = set()
    for sport, hook in hooks.items():
        if not hook:
            failures.add(sport)
            print(f"{sport}: results webhook missing")
            continue
        for row in rows:
            if row["sport"] != sport or row["outcome"] is None:
                continue
            key = (f"StatRally Even/Odd result test | {sport} | {os.environ['GITHUB_RUN_ID']}"
                   if args.test else f"StatRally Even/Odd result | {row['forecast']['id']}")
            try:
                status = deliver(repo, issues, key, hook, card(row, test=args.test))
                print(f"{sport}: {status}")
            except Exception as exc:
                failures.add(sport)
                print(f"{sport}: results delivery failed ({type(exc).__name__})")
    if failures:
        raise RuntimeError("Results routes failed: " + ", ".join(sorted(failures)))


if __name__ == "__main__":
    main()
