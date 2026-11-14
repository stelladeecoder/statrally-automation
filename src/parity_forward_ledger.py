"""Durable prematch parity forecasts and separately verified outcome grades.

GitHub issue body stores original predictions before Discord delivery.
Results are added as immutable bot-authored issue comments. No changes to BTTS.
"""
import argparse
import json
import os
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path
from parity_discord import github,BOT,render
from parity_research import LEAGUES,parse_time,fetch_scoreboard

PREFIX="statrally-parity-forecasts-v1:"
GRADE="statrally-parity-grade-v1:"
TITLE="StatRally parity forecasts | "

def check_report(report):
    render(report)
    if report.get("markets_verified") is not False or report.get("prices_verified") is not False:
        raise ValueError("Cannot archive unreviewed market status")
    if not isinstance(report.get("generated_at"),str):
        raise ValueError("Missing generation time")
    observed=parse_time(report["generated_at"])
    if observed.date()<datetime.fromisoformat(report["day_central"]).date()-timedelta(days=1):
        raise ValueError("Stale research report")
    fixtures=[]
    seen=set()
    for league in report["competitions"]:
        key=league["league"]
        if key not in LEAGUES or league["category"]!=LEAGUES[key][3]:
            raise ValueError("Unknown or misclassified competition")
        for record in league["fixtures"]:
            if record["id"] in seen:
                raise ValueError("Duplicate forecast fixture")
            seen.add(record["id"])
            stamp=parse_time(record["kickoff_utc"])
            if stamp<=observed:
                raise ValueError("Cannot record a post-kickoff prediction")
            if not isinstance(record.get("home_team_id"),str) or not isinstance(record.get("away_team_id"),str) or not record["home_team_id"].isdigit() or not record["away_team_id"].isdigit() or record["home_team_id"]==record["away_team_id"]:
                raise ValueError("Missing stable team IDs")
            p=record["forecast"]
            if p.get("qualified_bet") is not False or p.get("status") not in ("research_prediction","insufficient_history"):
                raise ValueError("Invalid research prediction")
            if p["status"]=="research_prediction":
                for name in ("p_even","p_odd"):
                    if type(p.get(name)) not in (float,int) or not 0<p[name]<1:
                        raise ValueError("Invalid issued parity probability")
                if abs(p["p_even"]+p["p_odd"]-1)>1e-6 or parse_time(p["as_of_utc"])>observed:
                    raise ValueError("Probability mass or future as-of mismatch")
            fixtures.append({"id":record["id"],"league":key,"sport":LEAGUES[key][0],
                "category":league["category"],"settlement_basis":league["settlement_basis"],
                "home":record["home"],"away":record["away"],
                "home_team_id":record["home_team_id"],"away_team_id":record["away_team_id"],
                "kickoff_utc":record["kickoff_utc"],"forecast":p})
    return {"schema_version":1,"status":"unpromoted_forward_research",
        "day_central":report["day_central"],"generated_at":report["generated_at"],
        "qualified_bets":0,"trades_placed":0,"fixtures":fixtures}

def issues(repo,*,call=github):
    result=[]
    for page in range(1,11):
        rows=call("GET",repo,f"/issues?state=all&per_page=100&page={page}")
        if not isinstance(rows,list):
            raise ValueError("Issue history is unavailable")
        result.extend(x for x in rows if "pull_request" not in x and (x.get("title") or "").startswith(TITLE))
        if len(rows)<100:
            return result
    raise ValueError("Issue history pagination incomplete")

def verify_issue(issue):
    if issue.get("user",{}).get("login")!=BOT:
        raise ValueError("Untrusted parity forecast issue")
    body=issue.get("body") or ""
    if not body.startswith(PREFIX):
        raise ValueError("Malformed parity issue")
    record=json.loads(body[len(PREFIX):])
    if (record.get("schema_version")!=1 or record.get("status")!="unpromoted_forward_research"
        or record.get("qualified_bets")!=0 or record.get("trades_placed")!=0):
        raise ValueError("Invalid archived forecast")
    if issue.get("title")!=TITLE+record.get("day_central",""):
        raise ValueError("Issue title/date mismatch")
    return record

def archive(report,repo,*,call=github):
    record=check_report(report)
    key=TITLE+record["day_central"]
    body=PREFIX+json.dumps(record,sort_keys=True,separators=(",",":"))
    if len(body)>60000:
        raise ValueError("Forward slate exceeds safe Github issue length; split before publishing")
    matched=[x for x in issues(repo,call=call) if x.get("title")==key]
    if len(matched)>1:
        raise ValueError("Duplicate forward archive issues")
    if matched:
        previous=verify_issue(matched[0])
        # A same-day re-run cannot silently replace original odds.
        if previous!=record:
            print("PARITY_ARCHIVE_PREVIOUSLY_FROZEN",matched[0]["number"])
            return {"status":"already_frozen","issue_number":matched[0]["number"]}
        return {"status":"already_frozen","issue_number":matched[0]["number"]}
    created=call("POST",repo,"/issues",{"title":key,"body":body})
    if not isinstance(created,dict) or type(created.get("number")) is not int:
        raise ValueError("Forward archive creation unconfirmed")
    print("PARITY_ARCHIVE_FROZEN",created["number"],len(record["fixtures"]))
    return {"status":"frozen","issue_number":created["number"],
            "forecasts":len(record["fixtures"])}

def verified_result(item,*,fetch=fetch_scoreboard,now=None,cache=None):
    now=now or datetime.now(timezone.utc)
    kick=parse_time(item["kickoff_utc"])
    if kick>=now:
        return {"status":"pending"}
    if item["league"] not in LEAGUES or item["settlement_basis"]!=LEAGUES[item["league"]][4]:
        raise ValueError("Unreviewed league or settlement scope")
    cache={} if cache is None else cache
    failure=False
    for offset in (0,-1,1):
        day=kick.date()+timedelta(days=offset)
        key=item["league"],day
        if key not in cache:
            try:cache[key]=fetch(item["league"],day,day)
            except (OSError,RuntimeError,ValueError) as exc:cache[key]=exc
        rows=cache[key]
        if isinstance(rows,Exception):
            failure=True
            continue
        matches=[r for r in rows if r["id"]==item["id"]]
        if len(matches)>1:raise ValueError("Ambiguous final event identity")
        if not matches:continue
        row=matches[0]
        if (row["home_team_id"]!=item["home_team_id"] or row["away_team_id"]!=item["away_team_id"]
            or row["home"]!=item["home"] or row["away"]!=item["away"]
            or parse_time(row["kickoff_utc"])!=kick
            or row["settlement_basis"]!=item["settlement_basis"]):
            raise ValueError("Historical fixture identity or kickoff mismatch")
        if row["status"]=="graded":
            return {"status":"graded","actual":row["parity"],
                    "total":row["score_total"],"source":row["source"]}
        return {"status":"pending","reason":row["status"]}
    return {"status":"provider_unavailable" if failure else "unconfirmed"}

def grade_repo(repo,*,now=None,call=github,fetch=fetch_scoreboard,lookback=4):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None or not 1<=lookback<=7:
        raise ValueError("Timezone-aware results grading and 1-7 day horizon required")
    # At most the recent local calendar days; older delayed games require manual regrade.
    from parity_research import CENTRAL
    local=now.astimezone(CENTRAL).date()
    selected=[]
    for issue in issues(repo,call=call):
        day=(issue.get("title") or "").removeprefix(TITLE)
        try:date=datetime.fromisoformat(day).date()
        except ValueError:continue
        if timedelta(days=0)<=local-date<=timedelta(days=lookback):
            selected.append((issue,verify_issue(issue)))
    cache={}
    counts=Counter()
    metrics={}
    for issue,record in selected:
        number=issue["number"]
        comments=[]
        for page in range(1,11):
            batch=call("GET",repo,f"/issues/{number}/comments?per_page=100&page={page}")
            if not isinstance(batch,list):raise ValueError("Grade comment history unavailable")
            comments+=batch
            if len(batch)<100:break
        else:raise ValueError("Grade comment history incomplete")
        existing={}
        for comment in comments:
            body=comment.get("body") or ""
            if not body.startswith(GRADE):
                continue
            if comment.get("user",{}).get("login")!=BOT:
                raise ValueError("Untrusted grading comment")
            outcome=json.loads(body[len(GRADE):])
            game_id=outcome.get("id")
            if game_id in existing:
                raise ValueError("Duplicate immutable grade")
            if outcome.get("status")!="graded" or outcome.get("actual") not in ("EVEN","ODD"):
                raise ValueError("Invalid archived parity grade")
            existing[game_id]=outcome
        for item in record["fixtures"]:
            game_id=item["id"]
            if game_id in existing:
                actual=existing[game_id]["actual"]
                if item["forecast"]["status"]=="research_prediction":
                    metrics[game_id]=(item["league"],item["forecast"]["p_even"],int(actual=="EVEN"))
                counts["previously_graded"]+=1
                continue
            result=verified_result(item,fetch=fetch,now=now,cache=cache)
            if result["status"]!="graded":
                counts[result["status"]]+=1
                continue
            proof={"id":game_id,"status":"graded","actual":result["actual"],
                   "total":result["total"],"source":result["source"]}
            response=call("POST",repo,f"/issues/{number}/comments",
                {"body":GRADE+json.dumps(proof,sort_keys=True,separators=(",",":"))})
            if type(response.get("id")) is not int:
                raise ValueError("Grade persistence unconfirmed")
            counts["newly_graded"]+=1
            if item["forecast"]["status"]=="research_prediction":
                metrics[game_id]=(item["league"],item["forecast"]["p_even"],int(result["actual"]=="EVEN"))
    import math
    summary={}
    for league in sorted({value[0] for value in metrics.values()}):
        rows=[(p,y) for lg,p,y in metrics.values() if lg==league]
        n=len(rows)
        summary[league]={"n":n,
            "accuracy":round(sum((p>=.5)==bool(y) for p,y in rows)/n,6),
            "even_accuracy":round(sum((p>=.5) and y==1 for p,y in rows)/max(1,sum(p>=.5 for p,_ in rows)),6)
                  if any(p>=.5 for p,_ in rows) else None,
            "odd_accuracy":round(sum((p<.5) and y==0 for p,y in rows)/max(1,sum(p<.5 for p,_ in rows)),6)
                  if any(p<.5 for p,_ in rows) else None,
            "brier":round(sum((p-y)**2 for p,y in rows)/n,6),
            "log_loss":round(-sum(y*math.log(p)+(1-y)*math.log(1-p) for p,y in rows)/n,6)}
    return {"status":"forward_research_only","days_checked":len(selected),
        "counts":dict(counts),"performance_by_league":summary,
        "qualified_bets":0,"trades_placed":0}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("archive","grade"))
    parser.add_argument("--report",default="out/statrally-parity-research.json")
    parser.add_argument("--output",default="out/statrally-parity-results.json")
    args=parser.parse_args()
    repo=os.environ["GITHUB_REPOSITORY"]
    if args.action=="archive":
        report=json.loads(Path(args.report).read_text(encoding="utf-8"))
        print("PARITY_FORWARD_ARCHIVE="+json.dumps(archive(report,repo),sort_keys=True))
    else:
        outcome=grade_repo(repo)
        dest=Path(args.output)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(outcome,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print("PARITY_FORWARD_RESULTS="+json.dumps(outcome,sort_keys=True))
if __name__=="__main__":
    main()
