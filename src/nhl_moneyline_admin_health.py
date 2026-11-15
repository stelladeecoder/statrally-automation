"""Read PRIVATE NHL moneyline poll receipts into the existing #admin daily report.

Uses existing STATRALLY_MODELS_READ_TOKEN; never copies private issue content to
the public automation repository. Only aggregated status counts are exposed.
Missing receipt history is NOT reported as zero successful or missed snapshots.
"""
import json
import os
from collections import defaultdict
from datetime import date, datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

REPO = "stelladeecoder/statrally-even-odd-models"
PREFIX = "statrally-nhl-moneyline-poller-health-v1:"
TITLE = "StatRally NHL Moneyline Poller Health | "
BOT = "github-actions[bot]"

def fetch(path, *, token, opener=urlopen):
    if not token:
        raise ValueError("Private NHL read token missing")
    if not path.startswith(("/issues?", "/issues/")):
        raise ValueError("Private NHL health read-only issues API only")
    url = "https://api.github.com/repos/" + REPO + path
    request = Request(url,method="GET",headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "StatRally-NHL-Admin-Health/1"})
    with opener(request,timeout=25) as response:
        return json.load(response)

def obtain(day, *, token, call=fetch):
    date.fromisoformat(str(day))
    name = TITLE + str(day)
    issue = None
    for page in range(1,21):
        rows=call(f"/issues?state=all&per_page=100&page={page}",token=token)
        if not isinstance(rows,list):
            raise ValueError("Private NHL issues query invalid")
        matches=[r for r in rows if r.get("title")==name and "pull_request" not in r]
        if len(matches)>1:
            raise ValueError("Duplicate private NHL health days")
        if matches:
            issue=matches[0]
            break
        if len(rows)<100:break
    else:
        raise ValueError("Private NHL health pagination exhausted")
    if issue is None:
        return None
    if (issue.get("user",{}).get("login")!=BOT
        or not str(issue.get("body","")).startswith(PREFIX)):
        raise ValueError("NHL health issue author or prefix not verified")
    data=[]
    for page in range(1,21):
        rows=call(f"/issues/{issue['number']}/comments?per_page=100&page={page}",token=token)
        if not isinstance(rows,list):
            raise ValueError("Private NHL health comments invalid")
        for comment in rows:
            if (comment.get("user",{}).get("login")!=BOT or
                not str(comment.get("body","")).startswith(PREFIX)):
                continue
            record=json.loads(comment["body"][len(PREFIX):])
            if (record.get("paper_only") is not True
                or record.get("orders_placed")!=0
                or record.get("workflow")!="nhl-moneyline-five-minute-paper-poller.yml"):
                raise ValueError("Untrusted private NHL poll receipt")
            events=record.get("events")
            if not isinstance(events,list):
                raise ValueError("Missing NHL poll events")
            data.append(record)
        if len(rows)<100:
            break
    else:
        raise ValueError("Private NHL daily poll receipts pagination limit exceeded")
    return data

def aggregate(records):
    if records is None:
        return None
    if not records:
        return {"polls":0,"entry_hits":0,"close_hits":0,"entry_misses":0,
                "close_misses":0,"kalshi_api_skips":0,"low_liquidity_skips":0,
                "model_source_errors":0,"identity_skips":0,"poll_failures":0}
    # Stage and contract must be unique for HIT counts, even after workflow
    # replay. A later successful capture overrides a previous skipped attempt.
    stages=defaultdict(set)
    attempts=defaultdict(set)
    low=api=source=identity=fail=0
    seen_runs=set()
    for r in records:
        run=str(r.get("run_id",""))
        if not run or run in seen_runs:
            raise ValueError("Duplicate or unidentified private NHL poll receipt")
        seen_runs.add(run)
        if r.get("poll_status") in ("failed","model_error","provider_error"):
            fail+=1
        for e in r["events"]:
            stage=e.get("stage")
            status=e.get("status","")
            fixture=str(e.get("fixture_id",""))
            ticker=str(e.get("contract", ""))
            if status in ("low_liquidity_skip","low_liquidity_skip_close"):
                low+=1
            if status in ("kalshi_api_error","kalshi_or_github_api_error",
                          "identity_or_api_error"):
                api+=1
            if status in ("model_data_error","model_missing_fixture"):
                source+=1
            if status=="identity_skip":
                identity+=1
            if stage in ("entry","close") and fixture:
                key=(fixture,ticker if ticker else "fixture")
                attempts[stage].add(key)
                if status==stage+"_hit" or status==stage+"_duplicate":
                    stages[stage].add(key)
    return {"polls":len(seen_runs),
            "entry_hits":len(stages["entry"]),
            "close_hits":len(stages["close"]),
            "entry_misses":len(attempts["entry"]-stages["entry"]),
            "close_misses":len(attempts["close"]-stages["close"]),
            "kalshi_api_skips":api,"low_liquidity_skips":low,
            "model_source_errors":source,"identity_skips":identity,
            "poll_failures":fail}

def lines_for_day(day, *, token, call=fetch):
    if not token:
        return ["NHL Moneyline [PAPER] snapshots: PRIVATE READ TOKEN MISSING; health unverified."]
    try:
        values=aggregate(obtain(day,token=token,call=call))
    except Exception as error:
        # No sensitive API URL or token in admin Discord messages.
        return [f"NHL Moneyline [PAPER] snapshots: HEALTH READ ERROR ({type(error).__name__}); verify private access."]
    if values is None:
        return ["NHL Moneyline [PAPER] snapshots: no private daily health issue found; unknown, NOT zero misses."]
    return [
        f"NHL Moneyline [PAPER] 5-min poll receipts: {values['polls']}; failures: {values['poll_failures']}",
        f"Entry snapshot contract hits/misses: {values['entry_hits']}/{values['entry_misses']}",
        f"Pre-puck closing snapshot contract hits/misses: {values['close_hits']}/{values['close_misses']}",
        f"Kalshi/API skips: {values['kalshi_api_skips']} | low-liquidity skips: {values['low_liquidity_skips']}",
        f"Model/source errors: {values['model_source_errors']} | identity skips: {values['identity_skips']}",
        "Misses above reflect observed attempts; absent scheduler runs may hide more misses."
    ]

if __name__=="__main__":
    today=os.environ.get("NHL_REPORT_DAY")
    if not today:
        raise SystemExit("NHL_REPORT_DAY required")
    for line in lines_for_day(today,token=os.environ.get("STATRALLY_MODELS_READ_TOKEN","")):
        print(line)
