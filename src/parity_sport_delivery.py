"""Independent sport-specific parity Discord delivery with no hidden fixtures.

Each sport has its own daily reservation and can fail without preventing
the other sport from attempting its delivery. One blue Discord embed per
sport where possible; paginated embeds only when necessary.
"""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from parity_discord import discord_send,github,BOT
from parity_research import LEAGUES

PREFIX="statrally-parity-sport-v2:"
SPORTS={"soccer":"⚽ Soccer","hockey":"🏒 NHL"}
BLUE=0x3498db
MAX_DESC=3600

def check(report):
    if (not isinstance(report,dict) or report.get("schema_version")!=1 or
        report.get("market")!="TOTAL_SCORE_PARITY" or report.get("status")!="research_only" or
        report.get("models_promoted") is not False or report.get("markets_verified") is not False or
        report.get("qualified_bets")!=0 or report.get("trades_placed")!=0):
        raise ValueError("Unapproved parity delivery source")
    comps=report.get("competitions")
    if not isinstance(comps,list) or not comps:
        raise ValueError("No verified sport coverage")
    seen=set()
    for comp in comps:
        code=comp.get("league")
        if code not in LEAGUES or code in seen:
            raise ValueError("Unknown or duplicate competition")
        seen.add(code)
        if (comp.get("category")!=LEAGUES[code][3] or
            comp.get("pregame_count")!=len(comp.get("fixtures",[]))):
            raise ValueError("Unverified competition or fixture count")
        for game in comp["fixtures"]:
            p=game.get("forecast")
            if not isinstance(p,dict) or p.get("qualified_bet") is not False or p.get("status") not in ("research_prediction","insufficient_history"):
                raise ValueError("Unverified market or probability state")
            if p["status"]=="research_prediction":
                if any(type(p.get(k)) not in (float,int) or not 0<p[k]<1 for k in ("p_even","p_odd")) or abs(p["p_even"]+p["p_odd"]-1)>1e-5:
                    raise ValueError("Unverified parity probability")
    return comps

def pages(report,sport):
    if sport not in SPORTS:
        raise ValueError("Unsupported sport")
    comps=[c for c in check(report) if LEAGUES[c["league"]][0]==sport]
    if not comps:
        raise ValueError("Missing selected sport data")
    total=sum(len(c["fixtures"]) for c in comps)
    body=[]
    for comp in comps:
        label=comp["competition_name"]+(" (Women)" if comp["category"]=="women" else "")
        body.append(f"**{label}** · {len(comp['fixtures'])} games")
        for game in comp["fixtures"]:
            timestamp=datetime.fromisoformat(game["kickoff_utc"].replace("Z","+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError("Unverified kickoff clock")
            # Watchlists show schedule only. Probabilities and market prices
            # belong exclusively in approved picks posts, not watchlists.
            body.append(f"• {game['away']} @ {game['home']} · <t:{int(timestamp.timestamp())}:t>")
    # Keep complete records, never replace missing rows with 'and N more'.
    batches=[]
    current=[]
    for line in body:
        if len(line)>MAX_DESC:
            raise ValueError("A fixture is too long to display")
        if len("\n".join(current+[line]))>MAX_DESC and current:
            batches.append("\n".join(current))
            current=[]
        current.append(line)
    if current:batches.append("\n".join(current))
    if not batches:batches=["No verified upcoming fixtures for this sport."]
    if len(batches)>10:
        raise ValueError("Too many Discord pages; archive retained, no partial send")
    payloads=[]
    for index,description in enumerate(batches,1):
        qualifier=f" · {index}/{len(batches)}" if len(batches)>1 else ""
        payloads.append({"embeds":[{
            "title":f"{SPORTS[sport]} Watchlist | {report['day_central']} CT{qualifier}",
            "description":description,
            "color":BLUE,
            "footer":{"text":f"{total} upcoming {sport} games · Schedule only · No probabilities or betting odds · Not picks"}
        }],"allowed_mentions":{"parse":[]}})
    # Check every fixture appears exactly once, even when paginated.
    all_text="\n".join(p["embeds"][0]["description"] for p in payloads)
    expected=[f"• {g['away']} @ {g['home']} · " for comp in comps for g in comp["fixtures"]]
    if any(all_text.count(label)!=expected.count(label) for label in set(expected)):
        raise ValueError("Discord pages dropped or duplicated fixture rows")
    return payloads

def _issue_for(repo,title,*,call):
    for page in range(1,11):
        rows=call("GET",repo,f"/issues?state=all&per_page=100&page={page}")
        if not isinstance(rows,list):raise ValueError("Cannot inspect delivery history")
        matches=[x for x in rows if "pull_request" not in x and x.get("title")==title]
        if len(matches)>1:raise ValueError("Duplicate sport delivery state")
        if matches:
            item=matches[0]
            if item.get("user",{}).get("login")!=BOT or not (item.get("body") or "").startswith(PREFIX):
                raise ValueError("Untrusted delivery reservation")
            return item,False
        if len(rows)<100:break
    else:raise ValueError("Delivery history pagination incomplete")
    item=call("POST",repo,"/issues",{"title":title,
        "body":PREFIX+json.dumps({"status":"reserved_before_discord","title":title},sort_keys=True)})
    if type(item.get("number")) is not int:raise ValueError("Unconfirmed reservation")
    return item,True

def send_sport(report,sport,repo,webhook,*,call=github,sender=discord_send):
    payloads=pages(report,sport)
    if not webhook:
        return {"sport":sport,"status":"webhook_missing","delivered":0,"pages":len(payloads)}
    title=f"StatRally parity {sport} | {report['day_central']}"
    issue,created=_issue_for(repo,title,call=call)
    if not created:
        return {"sport":sport,"status":"previously_reserved_no_retry","delivered":0,"pages":len(payloads)}
    # Reservation is durable before any Discord HTTP request.
    receipts=[]
    for position,payload in enumerate(payloads,1):
        # An ambiguous send is intentionally NOT retried.
        message_id=sender(webhook,payload)
        receipts.append(message_id)
        proof=call("POST",repo,f"/issues/{issue['number']}/comments",{
            "body":PREFIX+json.dumps({"page":position,"pages":len(payloads),
                  "message_id":message_id,"status":"confirmed"},sort_keys=True)})
        if type(proof.get("id")) is not int:
            raise ValueError("Delivered page receipt could not be persisted")
    call("PATCH",repo,f"/issues/{issue['number']}",{
       "state":"closed",
       "body":PREFIX+json.dumps({"status":"confirmed","pages":len(payloads),
             "message_ids":receipts,"title":title},sort_keys=True)})
    return {"sport":sport,"status":"confirmed","delivered":len(receipts),"pages":len(payloads)}

def destinations(environment):
    """NHL research belongs only in #nhl-watchlist, not picks or results."""
    soccer=(environment.get("STATRALLY_PARITY_SOCCER_WEBHOOK")
            or environment.get("STATRALLY_PARITY_DISCORD_WEBHOOK",""))
    # Explicitly route the research slate to the owner's existing #nhl-watchlist.
    # Legacy generic hockey webhook must not silently override the channel.
    hockey=environment.get("STATRALLY_NHL_WATCHLIST_WEBHOOK","")
    # Do not fall back to the shared channel for hockey.
    if soccer and hockey and soccer.strip()==hockey.strip():
        raise ValueError("Soccer and NHL webhooks cannot be identical")
    return {"soccer":soccer,"hockey":hockey}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--report",default="out/statrally-parity-research.json")
    parser.add_argument("--send",action="store_true")
    args=parser.parse_args()
    report=json.loads(Path(args.report).read_text(encoding="utf-8"))
    if not args.send:
        for sport in SPORTS:
            print("PARITY_SPORT_PREVIEW="+json.dumps({"sport":sport,"pages":pages(report,sport)}))
        return
    repo=os.environ["GITHUB_REPOSITORY"]
    failed=[]
    routes=destinations(os.environ)
    for sport in SPORTS:
        webhook=routes[sport]
        try:
            status=send_sport(report,sport,repo,webhook)
            print("PARITY_SPORT_DELIVERY="+json.dumps(status,sort_keys=True))
            if status["status"] not in ("confirmed","previously_reserved_no_retry"):
                failed.append(sport)
        except Exception as exc:
            failed.append(sport)
            print("PARITY_SPORT_DELIVERY_FAILED="+json.dumps({"sport":sport,"reason":type(exc).__name__}))
    if failed:
        raise RuntimeError("Sport-specific parity delivery not confirmed: "+",".join(failed))

if __name__=="__main__":
    main()
