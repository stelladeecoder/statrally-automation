"""Dedicated model-only EVEN/ODD research picks Discord delivery.

No EV, sportsbook pricing, market matching, profit claims or bet-placement.
Publish only timestamped pregame classifications from the independently
verified private model artifact. Watchlists stay schedule-only.
"""
import argparse
import json
import os
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from parity_discord import github,discord_send,BOT
from parity_model_handoff_consumer import stamp

BLUE=0x3498db
PREFIX="statrally-evenodd-research-picks-v1:"
MAX_DESC=3300
SPORTS={"soccer":"⚽ SOCCER","hockey":"🏒 NHL"}

def cards(projection,sport,*,now=None):
    now=now or datetime.now(timezone.utc)
    if sport not in SPORTS or not isinstance(projection,dict):
        raise ValueError("Unknown sport or predictions")
    if (projection.get("schema_version")!=1
        or projection.get("status")!="research_only_not_promoted"
        or projection.get("source_repository")!="stelladeecoder/statrally-even-odd-models"
        or projection.get("calibrated") is not False
        or projection.get("qualified_bets")!=0
        or projection.get("production_enabled") is not False):
        raise ValueError("Unverified Even/Odd model handoff")
    issued=stamp(projection["exported_at"])
    if issued>now or (now-issued).total_seconds()>86400:
        raise ValueError("Stale or future-issued model report")
    selections=[]
    seen=set()
    for row in projection["forecasts"]:
        if row["sport"]!=sport or row["status"]!="research_forecast_not_promoted":
            continue
        if (row["id"] in seen
            or row.get("calibration_evaluated") is not True
            or row.get("prediction") not in ("EVEN","ODD")
            or not isinstance(row.get("home"),str)
            or not isinstance(row.get("away"),str)):
            raise ValueError("Unverified prediction identity or model")
        seen.add(row["id"])
        kickoff=stamp(row["kickoff_utc"])
        forecasted=stamp(row["issued_at"])
        if (forecasted!=issued or kickoff<=now
            or kickoff.astimezone(ZoneInfo("America/Chicago")).date().isoformat()
               !=projection["input_day"]):
            # Only today's genuinely pregame fixtures; future-date games
            # receive their own subsequent daily picks, never today's label.
            continue
        p=row["p_even"] if row["prediction"]=="EVEN" else row["p_odd"]
        if type(p) not in (float,int) or not 0<p<1:
            raise ValueError("Invalid probability evidence")
        selections.append((row,kickoff,p))
    if not selections:
        return []
    selections.sort(key=lambda x:(x[1],x[0]["id"]))
    lines=[f"**{len(selections)} UPCOMING MODEL PREDICTIONS**",
           "**Research beta** · EVEN/ODD classification only",
           ""]
    for row,kickoff,p in selections:
        side=row["prediction"]
        lines.extend([f"**{row['away']} @ {row['home']}** · <t:{int(kickoff.timestamp())}:t>",
                      f"**{side}**  ·  Model estimate {p:.1%}",
                      ""])
    batches=[]
    part=[]
    for line in lines:
        candidate="\n".join(part+[line])
        if len(candidate)>MAX_DESC and part:
            batches.append("\n".join(part))
            part=[]
        if len(line)>MAX_DESC:
            raise ValueError("Oversized prediction label")
        part.append(line)
    if part:batches.append("\n".join(part))
    if len(batches)>10:
        raise ValueError("Too many Discord pages")
    payload=[]
    for i,body in enumerate(batches,1):
        label=f"  •  {i}/{len(batches)}" if len(batches)>1 else ""
        payload.append({"embeds":[{
            "title":f"{SPORTS[sport]} | EVEN/ODD PICKS{label}",
            "description":body,
            "color":BLUE,
            "fields":[{"name":"📆 Date (Central)","value":projection["input_day"],"inline":True},
                      {"name":"🧪 Type","value":"Experimental model classifications","inline":True}],
            "footer":{"text":"StatRally research • Historical calibration evaluated • Accuracy not established • No odds"}
        }],"allowed_mentions":{"parse":[]}})
    return payload

def _reserve(repo,key,*,call=github):
    for page in range(1,11):
        existing=call("GET",repo,f"/issues?state=all&per_page=100&page={page}")
        if not isinstance(existing,list):
            raise ValueError("Cannot audit Discord delivery reservations")
        matches=[x for x in existing if x.get("title")==key and "pull_request" not in x]
        if len(matches)>1:
            raise ValueError("Ambiguous existing picks delivery")
        if matches:
            prior=matches[0]
            if prior.get("user",{}).get("login")!=BOT or not (prior.get("body") or "").startswith(PREFIX):
                raise ValueError("Untrusted existing picks receipt")
            return None
        if len(existing)<100:break
    else:
        raise ValueError("Picks reservation history pagination exhausted")
    created=call("POST",repo,"/issues",{"title":key,"body":PREFIX+
         json.dumps({"status":"reserved_before_discord","title":key},sort_keys=True)})
    if type(created.get("number")) is not int:
        raise ValueError("Picks reservation creation unconfirmed")
    return created["number"]

def publish_one(projection,sport,repo,webhook,*,now=None,call=github,sender=discord_send):
    parts=cards(projection,sport,now=now)
    if not parts:
        return {"sport":sport,"status":"no_unexpired_predictions","delivered":0}
    if not webhook:
        return {"sport":sport,"status":"dedicated_webhook_missing","delivered":0}
    key=f"StatRally EvenOdd {sport} model picks | {projection['input_day']}"
    issue=_reserve(repo,key,call=call)
    if issue is None:
        return {"sport":sport,"status":"previously_reserved_no_duplicate","delivered":0}
    receipts=[]
    for i,payload in enumerate(parts,1):
        mid=sender(webhook,payload)
        receipts.append(mid)
        comment=call("POST",repo,f"/issues/{issue}/comments",
            {"body":PREFIX+json.dumps({"page":i,"message_id":mid,"status":"confirmed"},sort_keys=True)})
        if type(comment.get("id")) is not int:
            raise ValueError("Discord sent but durable receipt missing; do not retry")
    updated=call("PATCH",repo,f"/issues/{issue}",{"state":"closed",
        "body":PREFIX+json.dumps({"status":"confirmed","message_ids":receipts,
                        "model_source_run":projection["source_run_id"]},sort_keys=True)})
    if updated.get("number")!=issue:
        raise ValueError("Discord delivered but final receipt not persisted")
    return {"sport":sport,"status":"confirmed","delivered":len(receipts),
            "message_ids":receipts}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",default="out/model-handoff-evidence.json")
    parser.add_argument("--send",action="store_true")
    args=parser.parse_args()
    report=json.loads(Path(args.input).read_text(encoding="utf-8"))
    routes={"soccer":os.environ.get("STATRALLY_SOCCER_EVENODD_PICKS_WEBHOOK",""),
            "hockey":os.environ.get("STATRALLY_NHL_PICKS_WEBHOOK","")}
    if routes["soccer"] and routes["hockey"] and routes["soccer"]==routes["hockey"]:
        raise ValueError("Soccer and NHL picks destinations must be distinct")
    forbidden={os.environ.get("STATRALLY_NHL_WATCHLIST_WEBHOOK",""),
               os.environ.get("STATRALLY_PARITY_SOCCER_WEBHOOK",""),
               os.environ.get("STATRALLY_PARITY_DISCORD_WEBHOOK","")}
    for sport,hook in routes.items():
        if hook and hook in forbidden:
            raise ValueError("Picks webhook cannot be a watchlist destination")
    blockers=[]
    for sport in SPORTS:
        if not args.send:
            print("EVENODD_PICKS_PREVIEW="+json.dumps({"sport":sport,
                "pages":cards(report,sport)},sort_keys=True))
            continue
        result=publish_one(report,sport,os.environ["GITHUB_REPOSITORY"],routes[sport])
        print("EVENODD_PICKS_DELIVERY="+json.dumps(result,sort_keys=True))
        if result["status"]=="dedicated_webhook_missing":
            blockers.append(sport)
    if blockers:
        # Do not suppress a sport with a correctly configured picks channel
        # just because the other sport is awaiting a separate webhook.
        raise ValueError("Dedicated Even/Odd picks webhooks not configured: "+",".join(blockers))
if __name__=="__main__":
    main()
