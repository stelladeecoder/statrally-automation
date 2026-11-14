"""Observe parity GitHub cron and Discord receipt; alert privately on confirmed gaps.

GitHub scheduled checks are best-effort. This cannot independently guarantee
that GitHub itself invokes the watchdog when its scheduler is unavailable.
"""
import json
import os
from datetime import datetime,date,time,timezone
from zoneinfo import ZoneInfo
from parity_discord import github,discord_send,reservation,BOT,RESERVATION
from parity_sport_delivery import PREFIX as SPORT_PREFIX

CENTRAL=ZoneInfo("America/Chicago")
WORKFLOW="parity-soccer-nhl-beta.yml"
START=date(2026,11,15)
DUE=time(8,0)

def inspect(now,runs,issues):
    if now.tzinfo is None:raise ValueError("Timezone-aware monitoring clock required")
    local=now.astimezone(CENTRAL)
    day=local.date()
    if day<START:return {"status":"not_due_before_initial_cron","day":str(day)}
    if local.time()<DUE:return {"status":"not_due_yet","day":str(day)}
    if not isinstance(runs,list) or not isinstance(issues,list):
        raise ValueError("Unverifiable automation history")
    todays=[]
    for run in runs:
        if run.get("event")!="schedule" or run.get("head_branch")!="main":
            continue
        if not run.get("created_at"):
            raise ValueError("Scheduled run has no timestamp")
        created=datetime.fromisoformat(run["created_at"].replace("Z","+00:00")).astimezone(CENTRAL).date()
        if created==day:todays.append(run)
    if not todays:return {"status":"missed_scheduled_run","day":str(day)}
    if any(x.get("conclusion")=="success" for x in todays):
        # Every sport must have a separately confirmed research delivery receipt.
        for sport in ("soccer","hockey"):
            title=f"StatRally parity {sport} | {day}"
            receipts=[x for x in issues if x.get("title")==title and "pull_request" not in x]
            if len(receipts)>1:raise ValueError("Duplicate sport-specific delivery receipts")
            if not receipts:
                return {"status":"scheduled_scan_succeeded_discord_unverified",
                        "day":str(day),"sport":sport}
            receipt=receipts[0]
            if receipt.get("user",{}).get("login")!=BOT or not (receipt.get("body") or "").startswith(SPORT_PREFIX):
                raise ValueError("Untrusted sport-specific Discord receipt")
            value=json.loads(receipt["body"][len(SPORT_PREFIX):])
            if (value.get("status")!="confirmed" or type(value.get("pages")) is not int
                    or value["pages"]<1 or not isinstance(value.get("message_ids"),list)
                    or len(value["message_ids"])!=value["pages"] or
                    any(not str(x).isdigit() for x in value["message_ids"])):
                return {"status":"scheduled_scan_succeeded_discord_unverified",
                        "day":str(day),"sport":sport}
        return {"status":"scheduled_scan_and_discord_confirmed","day":str(day)}
    if any(x.get("status") in ("queued","waiting","pending","in_progress") for x in todays):
        return {"status":"scheduled_scan_in_progress","day":str(day)}
    return {"status":"scheduled_scan_failed","day":str(day)}

def check(*,now=None,call=github,sender=discord_send):
    now=now or datetime.now(timezone.utc)
    repo=os.environ["GITHUB_REPOSITORY"]
    response=call("GET",repo,f"/actions/workflows/{WORKFLOW}/runs?per_page=100")
    if not isinstance(response,dict) or not isinstance(response.get("workflow_runs"),list):
        raise ValueError("Scheduled run history unavailable")
    issues=call("GET",repo,"/issues?state=all&per_page=100")
    if not isinstance(issues,list):
        raise ValueError("Discord delivery receipt history unavailable")
    result=inspect(now,response["workflow_runs"],issues)
    print("PARITY_SCHEDULER_AUDIT="+json.dumps(result,sort_keys=True))
    if result["status"] not in ("missed_scheduled_run",
        "scheduled_scan_failed","scheduled_scan_succeeded_discord_unverified"):
        return result
    webhook=os.environ.get("STATRALLY_ADMIN_DISCORD_WEBHOOK","")
    if not webhook:
        print("PARITY_ADMIN_WEBHOOK_NOT_CONFIGURED")
        return result
    key="StatRally parity health | "+result["day"]+" | "+result["status"]
    checkpoint=reservation(repo,key,call=call)
    if checkpoint is None:
        print("PARITY_HEALTH_ALERT_ALREADY_RESERVED")
        return result
    msg=("🚨 StatRally soccer/NHL Even/Odd "+result["status"].replace("_"," ")+
         " on "+result["day"]+" (Central). Check parity GitHub Actions and Discord receipts. "+
         "Do not blindly rerun uncertain deliveries or place bets.")
    receipt=sender(webhook,{"content":msg,"allowed_mentions":{"parse":[]}})
    call("PATCH",repo,f"/issues/{checkpoint}",{"state":"closed",
        "body":RESERVATION+json.dumps({"status":"confirmed","key":key,"message_id":receipt})})
    return result

if __name__=="__main__":
    check()
