"""Daily private report of verified forward Even/Odd performance."""
import math
import os
from datetime import date, datetime, timedelta, timezone

from parity_recaps import CENTRAL, SPORTS, collect, deliver, history, line


def card(title, sections):
    return {"title": title, "description": "\n\n".join(sections), "color": 0x3498DB}


def sport_card(label, rows):
    sections = [line("Cumulative accuracy", rows)]
    picks = lambda side: [row for row in rows if row["forecast"]["prediction"] == side]
    sections.append("**By predicted side**\n" + "\n".join(
        line(side, picks(side)) for side in ("EVEN", "ODD")))
    if rows:
        n = len(rows)
        correct = sum(row["correct"] for row in rows)
        odd = sum(row["outcome"]["actual"] == "ODD" for row in rows)
        assigned = [row["forecast"]["p_" + row["outcome"]["actual"].lower()] for row in rows]
        brier = sum((1 - p) ** 2 for p in assigned) / n
        loss = -sum(math.log(p) for p in assigned) / n
        sections.extend([
            f"**Against always picking ODD**\n{correct/n:.1%} model · {odd/n:.1%} baseline"
            f" · **{100*(correct-odd)/n:+.1f} percentage points**",
            f"**Probability quality**\nBrier score **{brier:.3f}** · Log loss **{loss:.3f}**",
        ])
    else:
        sections.append("**Baseline and probability quality**\nAwaiting verified finals.")
    sections.append(line("⭐ 70%+ picks", [row for row in rows if row["starred"]]))
    versions = sorted({row["forecast"]["model"] for row in rows})
    if versions:
        sections.append("**Model versions**\n" + "\n".join(f"`{version}`" for version in versions))
    return card(f"{label} | Cumulative", sections)


def report(rows, today):
    graded = [row for row in rows if row["correct"] is not None]
    latest = max((row["day"] for row in graded), default=None)
    recent = [row for row in graded if row["day"] == latest]
    scope = f"Updated {today:%B %d, %Y} · Central Time"
    daily = (f"**Latest graded day · {latest:%B %d}**\n" if latest else
             "**Latest graded day**\nAwaiting verified finals.\n")
    daily += "\n".join([line("Combined", recent)] + [
        line(label, [row for row in recent if row["sport"] == sport]) for sport, label in SPORTS])
    overview = card("📊 StatRally | Even/Odd Model Performance", [
        scope, daily, line("Cumulative combined", graded),
        "⭐ 🟨 **VERY HIGH MODEL PROBABILITY · 70%+**\n"
        + line("Cumulative combined", [row for row in graded if row["starred"]])
        + "\n*Included in overall accuracy. Descriptive only, not validated reliability.*",
    ])
    overview["footer"] = {"text": "Matched baseline uses the same games · Lower Brier and log loss are better · Forward calibration unvalidated"}
    return {"embeds": [overview] + [
        sport_card(label, [row for row in graded if row["sport"] == sport]) for sport, label in SPORTS],
        "allowed_mentions": {"parse": []}}


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    hook = os.environ.get("STATRALLY_MODEL_PERFORMANCE_DISCORD_WEBHOOK")
    if not hook:
        raise RuntimeError("Model performance Discord webhook is missing")
    now = datetime.now(timezone.utc)
    today = now.astimezone(CENTRAL).date()
    issues = [row for row in history(repo, "/issues?state=all") if "pull_request" not in row]
    rows = collect(repo, issues, date(2026, 11, 14), today - timedelta(days=1), now)
    status = deliver(repo, issues, "StatRally Even/Odd model performance", hook, report(rows, today))
    print(f"Model performance: {status}")


if __name__ == "__main__":
    main()
