"""Public read-only parity projection of stored pregame forecasts and verified grades.

Consumes only bot-authored GitHub Issues, never arbitrary private source fields.
Build output is a static JSON snapshot for the optional GitHub Pages dashboard.
"""
import argparse
import json
from datetime import datetime,timezone
from pathlib import Path
from parity_forward_ledger import issues,verify_issue,GRADE,BOT
from parity_discord import github
from parity_research import LEAGUES

def public_snapshot(repo,*,now=None,call=github):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError("Aware generation timestamp required")
    records=[]
    seen=set()
    for issue in issues(repo,call=call):
        record=verify_issue(issue)
        comments=[]
        for page in range(1,11):
            group=call("GET",repo,f"/issues/{issue['number']}/comments?per_page=100&page={page}")
            if not isinstance(group,list):raise ValueError("Unverified grade history")
            comments+=group
            if len(group)<100:break
        else:raise ValueError("Incomplete public grade pagination")
        outcomes={}
        for comment in comments:
            body=comment.get("body") or ""
            if not body.startswith(GRADE):continue
            if comment.get("user",{}).get("login")!=BOT:
                raise ValueError("Untrusted grader")
            value=json.loads(body[len(GRADE):])
            if value.get("status")!="graded" or value.get("actual") not in ("EVEN","ODD") or type(value.get("total")) is not int or value["total"]<0 or value["actual"]!=("EVEN" if value["total"]%2==0 else "ODD"):
                raise ValueError("Invalid historical parity proof")
            if value.get("id") in outcomes:raise ValueError("Duplicate grade")
            outcomes[value["id"]]=value
        fixture_ids={x["id"] for x in record["fixtures"]}
        if set(outcomes)-fixture_ids:raise ValueError("Unknown grade event identity")
        for fixture in record["fixtures"]:
            if fixture["id"] in seen:raise ValueError("Repeated forecast event in public history")
            seen.add(fixture["id"])
            lg=fixture["league"]
            if lg not in LEAGUES or fixture["category"]!=LEAGUES[lg][3]:
                raise ValueError("Invalid competition ID in public projection")
            forecast=fixture["forecast"]
            valid=forecast["status"]=="research_prediction"
            if forecast.get("qualified_bet") is not False:raise ValueError("Bet approval not allowed")
            grade=outcomes.get(fixture["id"])
            rows={"id":fixture["id"],"sport":fixture["sport"],"league":lg,
                  "competition":LEAGUES[lg][2],"category":fixture["category"],
                  "home":fixture["home"],"away":fixture["away"],
                  "kickoff_utc":fixture["kickoff_utc"],
                  "settlement_basis":fixture["settlement_basis"],
                  "issued_at":record["generated_at"],
                  "prediction_status":forecast["status"],
                  "p_even":forecast["p_even"] if valid else None,
                  "p_odd":forecast["p_odd"] if valid else None,
                  "grade_status":"graded" if grade else "pending",
                  "total":grade["total"] if grade else None,
                  "actual":grade["actual"] if grade else None}
            records.append(rows)
    records.sort(key=lambda x:(x["kickoff_utc"],x["id"]),reverse=True)
    metrics=[]
    for league in LEAGUES:
        rated=[x for x in records if x["league"]==league and x["grade_status"]=="graded"
               and x["prediction_status"]=="research_prediction"]
        predicted=[x for x in records if x["league"]==league and x["prediction_status"]=="research_prediction"]
        n=len(rated)
        metrics.append({"league":league,"competition":LEAGUES[league][2],
                        "category":LEAGUES[league][3],
                        "recorded":len(predicted),"graded":n,
                        "accuracy":round(sum((x["p_even"]>=.5)==(x["actual"]=="EVEN") for x in rated)/n,6) if n else None,
                        "brier":round(sum((x["p_even"]-int(x["actual"]=="EVEN"))**2 for x in rated)/n,6) if n else None})
    return {"schema_version":1,"market":"TOTAL_SCORE_PARITY","status":"forward_research_only",
            "generated_at":now.astimezone(timezone.utc).isoformat(),
            "qualified_bets":0,"trades_placed":0,
            "markets_verified":False,"models_calibrated":False,
            "records":records,"performance_by_league":metrics}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="out/statrally-parity-public.json")
    args=parser.parse_args()
    import os
    projection=public_snapshot(os.environ["GITHUB_REPOSITORY"])
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(projection,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8")
    print("PARITY_PUBLIC_SNAPSHOT="+json.dumps({"records":len(projection["records"]),
        "graded":sum(x["grade_status"]=="graded" for x in projection["records"]),
        "qualified_bets":0},sort_keys=True))
if __name__=="__main__":
    main()
