"""Discord-only research beta report with one durable GitHub reservation/day.

No wager picks. A missing Discord receipt cannot be automatically retried.
"""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError

RESERVATION="statrally-parity-beta-delivery-v1:"
BOT="github-actions[bot]"

def render(report):
    if not isinstance(report,dict) or report.get("schema_version")!=1 or report.get("market")!="TOTAL_SCORE_PARITY":
        raise ValueError("Unsupported parity report")
    if (report.get("status")!="research_only" or report.get("qualified_bets")!=0 or
            report.get("trades_placed")!=0 or report.get("models_promoted") is not False or
            report.get("markets_verified") is not False):
        raise ValueError("Research-only safety gate failed")
    competitions=report.get("competitions")
    if not isinstance(competitions,list) or not competitions or sorted(report.get("sports",[]))!=["hockey","soccer"]:
        raise ValueError("Both soccer and hockey sections are required")
    total=sum(len(x.get("fixtures",[])) for x in competitions)
    lines=[f"🏟️ **StatRally EVEN/ODD | Soccer + NHL | {report['day_central']} CT**",
           f"**{total} upcoming games** | **Research beta only, not betting picks**",
           "Probabilities are uncalibrated historical baselines. Markets/odds unverified."]
    for item in competitions:
        if item.get("pregame_count")!=len(item.get("fixtures",[])):
            raise ValueError("Coverage count mismatch")
        title=item["competition_name"]
        league=item["league"]
        if item.get("category")=="women":
            title+=" (Women)"
        lines.append(f"**{title}** | {len(item['fixtures'])} upcoming | {item['historical_games']} verified finals")
        for f in item["fixtures"][:4]:
            p=f["forecast"]
            if p.get("qualified_bet") is not False:
                raise ValueError("Unverified wager recommendation")
            if p.get("status")=="research_prediction":
                detail=f"Even {p['p_even']:.1%} / Odd {p['p_odd']:.1%}"
            elif p.get("status")=="insufficient_history":
                detail="Insufficient history"
            else:
                raise ValueError("Unreviewed probability status")
            when=datetime.fromisoformat(f["kickoff_utc"])
            lines.append(f"• {f['away']} @ {f['home']} | <t:{int(when.timestamp())}:t> | {detail}")
        if len(item["fixtures"])>4:
            lines.append(f"… and {len(item['fixtures'])-4} more {league} fixtures in audit report")
    lines.append("Soccer: 90 minutes; NHL: full final scoreboard incl. OT/SO when present. Exact sportsbook settlement unverified.")
    text="\n".join(lines)
    if len(text)>1900:
        # Render headline and competition coverage only, never truncate an identity.
        text="\n".join(lines[:3]+[f"• {x['competition_name']}: {len(x['fixtures'])} pregame, {x['historical_games']} finals" for x in competitions]+[
            "Research only. Full audited slate is available in GitHub Actions artifact."])
    if len(text)>1900:
        raise ValueError("Discord research message too large")
    return {"content":text,"allowed_mentions":{"parse":[]}}

def github(method,repo,path,data=None,*,opener=urlopen):
    token=os.environ["GH_TOKEN"]
    payload=json.dumps(data).encode() if data is not None else None
    req=Request(f"https://api.github.com/repos/{repo}{path}",data=payload,method=method,
        headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
                 "Content-Type":"application/json","X-GitHub-Api-Version":"2022-11-28"})
    with opener(req,timeout=25) as response:
        return json.load(response)

def reservation(repo,key,*,call=github):
    for page in range(1,11):
        issues=call("GET",repo,f"/issues?state=all&per_page=100&page={page}")
        if not isinstance(issues,list):
            raise ValueError("Unable to audit delivery reservations")
        for issue in issues:
            if "pull_request" in issue or issue.get("title")!=key:
                continue
            if issue.get("user",{}).get("login")!=BOT or not (issue.get("body") or "").startswith(RESERVATION):
                raise ValueError("Untrusted duplicate reservation")
            return None
        if len(issues)<100:
            break
    else:
        raise ValueError("Reservation history exceeded bounds")
    created=call("POST",repo,"/issues",{"title":key,
        "body":RESERVATION+json.dumps({"status":"reserved_before_http","key":key})})
    if type(created.get("number")) is not int:
        raise ValueError("Reservation not verified")
    return created["number"]

def discord_send(webhook,payload,*,opener=urlopen):
    url=urlsplit(webhook)
    if url.scheme!="https" or url.hostname not in ("discord.com","discordapp.com") or not url.path.startswith("/api/webhooks/"):
        raise ValueError("Discord webhook origin invalid")
    query=[(k,v) for k,v in parse_qsl(url.query) if k!="wait"]
    target=urlunsplit((url.scheme,url.netloc,url.path,urlencode(query+[("wait","true")]),""))
    req=Request(target,data=json.dumps(payload).encode(),method="POST",
        headers={"Content-Type":"application/json","User-Agent":"StatRallyParityResearch/0.1"})
    with opener(req,timeout=20) as response:
        if response.status!=200:
            raise ValueError("Discord receipt unconfirmed")
        body=response.read(65537)
    if len(body)>65536:
        raise ValueError("Oversized Discord response")
    receipt=json.loads(body)
    if not isinstance(receipt,dict) or not str(receipt.get("id","")).isdigit():
        raise ValueError("Discord message ID unconfirmed")
    return str(receipt["id"])

def publish(report,repo,webhook,*,call=github,sender=discord_send):
    payload=render(report)
    if not webhook:
        print("PARITY_DISCORD_NOT_CONFIGURED_DRY_RUN")
        return {"status":"not_configured"}
    key=f"StatRally parity research | {report['day_central']}"
    issue=reservation(repo,key,call=call)
    if issue is None:
        print("PARITY_DISCORD_ALREADY_RESERVED_NO_RETRY")
        return {"status":"previously_reserved"}
    receipt=sender(webhook,payload)
    call("PATCH",repo,f"/issues/{issue}",{"state":"closed",
        "body":RESERVATION+json.dumps({"status":"confirmed","message_id":receipt,"key":key})})
    print("PARITY_DISCORD_DELIVERED="+json.dumps({"status":"confirmed","message_id":receipt}))
    return {"status":"confirmed","message_id":receipt}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--report",default="out/statrally-parity-research.json")
    parser.add_argument("--send",action="store_true")
    args=parser.parse_args()
    report=json.loads(Path(args.report).read_text(encoding="utf-8"))
    payload=render(report)
    if not args.send:
        print(json.dumps(payload,sort_keys=True))
        return
    if not os.environ.get("GITHUB_REPOSITORY"):
        raise ValueError("GitHub repo must be supplied")
    publish(report,os.environ["GITHUB_REPOSITORY"],
            os.environ.get("STATRALLY_PARITY_DISCORD_WEBHOOK",""))

if __name__=="__main__":
    main()
