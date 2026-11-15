"""Publish Discord recaps from the verified private-model Even/Odd handoff."""
import calendar
import json
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from daily_results import edit_message
from parity_calendar import NAME as CALENDAR_NAME, render_calendar, upload_image
from m13_discord_embeds import CENTRAL
from parity_discord import BOT, discord_send, github
from parity_model_handoff_consumer import PREFIX, TITLE, stamp
from parity_prediction_delivery import VERY_HIGH_PROBABILITY
from parity_research import LEAGUES, fetch_scoreboard

GRADE = "statrally-evenodd-model-grade-v1:"
RECEIPT = "statrally-evenodd-recap-v1:"
RECAP_TITLE = "StatRally Even/Odd recap | "
SPORTS = (("soccer", "⚽ Soccer"), ("hockey", "🏒 NHL"))
HOOKS = {
    "daily": "STATRALLY_DAILY_RESULTS_DISCORD_WEBHOOK",
    "weekly": "STATRALLY_WEEKLY_RECAP_DISCORD_WEBHOOK",
    "monthly": "STATRALLY_MONTHLY_RECAP_DISCORD_WEBHOOK",
}


def history(repo, path):
    for page in range(1, 101):
        separator = "&" if "?" in path else "?"
        rows = github("GET", repo, f"{path}{separator}per_page=100&page={page}")
        if not isinstance(rows, list):
            raise RuntimeError("GitHub history unavailable")
        yield from rows
        if len(rows) < 100:
            return
    raise RuntimeError("GitHub history incomplete")


def periods(day):
    sunday = day - timedelta(days=(day.weekday() + 1) % 7)
    saturday = sunday - timedelta(days=1) if day.weekday() != 5 else day
    return {
        "daily": (day, day),
        "weekly": (saturday - timedelta(days=6), saturday),
        "monthly": (day.replace(day=1), day),
    }


def grade(row, cache, *, fetch=fetch_scoreboard):
    kickoff = stamp(row["kickoff_utc"])
    league = row["league"]
    for offset in (0, -1, 1):
        day = kickoff.date() + timedelta(days=offset)
        key = (league, day)
        if key not in cache:
            try:
                cache[key] = fetch(league, day, day)
            except (OSError, RuntimeError, ValueError):
                cache[key] = []
        matches = [event for event in cache[key] if event["id"] == row["id"]]
        if not matches:
            continue
        if len(matches) != 1:
            raise ValueError("Ambiguous ESPN event identity")
        event = matches[0]
        if (stamp(event["kickoff_utc"]) != kickoff
            or event["home"] != row["home"] or event["away"] != row["away"]
            or event["settlement_basis"] != LEAGUES[league][4]):
            return None
        if event["status"] == "graded":
            return {"actual": event["parity"], "total": event["score_total"],
                    "source": event["source"], "home_score": event.get("home_score"),
                    "away_score": event.get("away_score")}
        return None
    return None


def collect(repo, issues, start, end, now):
    slates = {}
    for issue in issues:
        title = issue.get("title") or ""
        if not title.startswith(TITLE) or issue["user"]["login"] != BOT:
            continue
        day = date.fromisoformat(title[len(TITLE):].split(" | ")[0])
        if start <= day <= end:
            prior = slates.get(day)
            if prior is None or issue["number"] > prior["number"]:
                slates[day] = issue

    results = []
    cache = {}
    seen = set()
    for day, issue in sorted(slates.items()):
        body = issue["body"]
        if not body.startswith(PREFIX):
            raise ValueError("Invalid archived model handoff")
        report = json.loads(body[len(PREFIX):])
        if (report["status"] != "research_only_not_promoted"
            or report["input_day"] != day.isoformat()
            or report["source_repository"] != "stelladeecoder/statrally-even-odd-models"):
            raise ValueError("Unverified model handoff")
        grades = {}
        for comment in history(repo, f"/issues/{issue['number']}/comments"):
            body = comment.get("body") or ""
            if not body.startswith(GRADE) or comment["user"]["login"] != BOT:
                continue
            outcome = json.loads(body[len(GRADE):])
            grades[outcome["id"]] = outcome
        for row in report["forecasts"]:
            if row["status"] != "research_forecast_not_promoted":
                continue
            kickoff = stamp(row["kickoff_utc"])
            if (kickoff.astimezone(CENTRAL).date() != day or kickoff > now
                or stamp(row["issued_at"]) >= kickoff or row["id"] in seen):
                continue
            seen.add(row["id"])
            outcome = grades.get(row["id"])
            if outcome is None:
                outcome = grade(row, cache)
                if outcome is not None:
                    outcome["id"] = row["id"]
                    saved = github("POST", repo, f"/issues/{issue['number']}/comments",
                                   {"body": GRADE + json.dumps(outcome, sort_keys=True)})
                    if type(saved.get("id")) is not int:
                        raise RuntimeError("Recap grade persistence unconfirmed")
            side = row["prediction"]
            results.append({
                "day": day, "sport": row["sport"], "forecast": row, "outcome": outcome,
                "starred": row["p_" + side.lower()] >= VERY_HIGH_PROBABILITY,
                "correct": None if outcome is None else outcome["actual"] == side,
            })
    return results


def tally(rows):
    counts = Counter(row["correct"] for row in rows)
    return counts[True], counts[True] + counts[False], counts[None]


def line(label, rows):
    correct, graded, pending = tally(rows)
    accuracy = f" · **{correct / graded:.1%}**" if graded else ""
    waiting = f" · {pending} pending" if pending else ""
    return f"**{label}** · {correct} correct / {graded} graded{accuracy}{waiting}"


def payload(kind, start, end, rows):
    title = {"daily": "Daily Recap", "weekly": "Weekly Recap",
             "monthly": f"{start:%B} Recap"}[kind]
    if kind == "daily":
        dates = f"{end:%A, %B} {end.day} · Central Time"
    elif kind == "weekly":
        dates = f"{start:%A, %B} {start.day} through {end:%A, %B} {end.day}"
    else:
        dates = f"Month to date through {end:%B} {end.day}"
    lines = [dates, "", line("Combined", rows)]
    lines.extend(line(label, [r for r in rows if r["sport"] == sport])
                 for sport, label in SPORTS)
    if kind == "monthly":
        lines.extend(["", "**Calendar · combined daily accuracy**",
                      "Green: 70%+ · Red: below 70% · Gray: no graded data"])
    stars = [r for r in rows if r["starred"]]
    lines.extend(["", "⭐ 🟨 **VERY HIGH MODEL PROBABILITY · 70%+**",
                  line("Combined", stars)])
    lines.extend(line(label, [r for r in stars if r["sport"] == sport])
                 for sport, label in SPORTS)
    lines.append("*Descriptive only, not validated reliability.*")
    embed = {"title": f"StatRally Even/Odd · {title}",
             "description": "\n".join(lines), "color": 0x3498DB}
    if kind == "monthly":
        embed["image"] = {"url": "attachment://" + CALENDAR_NAME}
    return {"embeds": [embed], "allowed_mentions": {"parse": []}}


def deliver(repo, issues, key, hook, message, *, calendar_image=None):
    import hashlib

    digest = hashlib.sha256(json.dumps(message, sort_keys=True).encode()).hexdigest()
    matches = [issue for issue in issues if issue.get("title") == key]
    if len(matches) > 1:
        raise ValueError("Duplicate recap receipts")
    if matches:
        issue = matches[0]
        if issue["user"]["login"] != BOT or not issue["body"].startswith(RECEIPT):
            raise ValueError("Untrusted recap receipt")
        receipt = json.loads(issue["body"][len(RECEIPT):])
        if receipt.get("digest") == digest:
            return "already_current"
        if "message_id" not in receipt:
            raise RuntimeError("Previous recap delivery requires reconciliation")
        if calendar_image is not None:
            upload_image(hook, message, calendar_image, receipt["message_id"])
        else:
            edit_message(message, hook, receipt)
        message_id = receipt["message_id"]
    else:
        issue = github("POST", repo, "/issues", {"title": key, "body": RECEIPT + "{}"})
        if type(issue.get("number")) is not int:
            raise RuntimeError("Recap reservation unconfirmed")
        message_id = (upload_image(hook, message, calendar_image)
                      if calendar_image is not None else discord_send(hook, message))
    updated = github("PATCH", repo, f"/issues/{issue['number']}", {
        "state": "closed",
        "body": RECEIPT + json.dumps({"message_id": message_id, "digest": digest}),
    })
    if updated.get("number") != issue["number"]:
        raise RuntimeError("Recap receipt persistence unconfirmed")
    print(f"Discord receipt {key}: {message_id}")
    return "confirmed"


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    now = datetime.now(timezone.utc)
    local_now = now.astimezone(CENTRAL)
    # Early-morning recovery completes the previous evening's reporting day.
    day = local_now.date() - timedelta(days=1) if local_now.hour < 8 else local_now.date()
    windows = periods(day)
    issues = [row for row in history(repo, "/issues?state=all") if "pull_request" not in row]
    rows = collect(repo, issues, min(start for start, _ in windows.values()), day, now)
    missing = []
    failed = []
    for kind, (start, end) in windows.items():
        hook = os.environ.get(HOOKS[kind])
        if not hook:
            missing.append(kind)
            continue
        selected = [r for r in rows if start <= r["day"] <= end]
        if not selected:
            print(f"{kind}: configured, no archived picks in period")
            continue
        key = f"{RECAP_TITLE}{kind} | {start}"
        try:
            image = render_calendar(start, end, selected) if kind == "monthly" else None
            result = deliver(repo, issues, key, hook, payload(kind, start, end, selected),
                             calendar_image=image)
            print(f"{kind}: {result}")
        except Exception as exc:
            failed.append(kind)
            print(f"{kind}: delivery failed ({type(exc).__name__})")
    if missing or failed:
        raise RuntimeError(f"Recap routes missing: {missing}. Delivery failed: {failed}.")


if __name__ == "__main__":
    main()
