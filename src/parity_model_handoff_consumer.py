"""Fail-closed private model artifact ingestion for public StatRally automation.

Cross-repository access requires a private fine-grained token with Actions
READ access to statrally-even-odd-models, stored as an Actions secret in
statrally-automation. Never automatically post research forecasts to Discord.
"""
import argparse
import io
import json
import math
import os
import re
import zipfile
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen,build_opener,HTTPRedirectHandler
from urllib.parse import urlsplit
from parity_discord import github,BOT

PRIVATE="stelladeecoder/statrally-even-odd-models"
CONTRACT="STATRALLY_EVEN_ODD_MODEL_HANDOFF_V1"
WORKFLOW="parity-model-handoff.yml"
PREFIX="statrally-parity-model-handoff-v1:"
TITLE="StatRally private parity model evidence | "
LEAGUES={
 "soccer_epl","soccer_bundesliga","soccer_laliga","soccer_serie_a",
 "soccer_ligue_1","soccer_eredivisie","soccer_liga_portugal",
 "soccer_brasileirao","soccer_mls","soccer_liga_mx",
 "soccer_primera_lpf","soccer_champions_league","soccer_europa_league"
}
ALLOWED_STATUS={"research_forecast_not_promoted","team_identity_unconfirmed",
                "kickoff_passed_without_pregame_model_issue",
                "insufficient_history","insufficient_team_history",
                "nonpositive_scoring_prior","insufficient_calibration"}

def stamp(value):
    if not isinstance(value,str):
        raise ValueError("Missing timestamp")
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Naive timestamp")
    return dt.astimezone(timezone.utc)

def validate(data,run,*,now=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None or not isinstance(data,dict) or not isinstance(run,dict):
        raise ValueError("Unverifiable model artifact")
    if (data.get("schema_version")!=1 or data.get("contract")!=CONTRACT
        or data.get("source_repository")!=PRIVATE
        or data.get("input_repository")!="stelladeecoder/statrally-automation"
        or data.get("model")!="team_poisson_parity_candidate_v1"
        or data.get("status")!="research_only_not_promoted"
        or data.get("validated_for_production") is not False
        or data.get("calibrated") is not False
        or data.get("markets_verified") is not False
        or data.get("qualified_bets")!=0 or data.get("trades_placed")!=0):
        raise ValueError("Unsafe model promotion or handoff contract")
    if (run.get("event") not in ("schedule","workflow_dispatch","push")
        or run.get("head_branch")!="main" or run.get("status")!="completed"
        or run.get("conclusion")!="success"
        or not re.fullmatch("[0-9a-f]{40}",str(run.get("head_sha","")))
        or data.get("source_commit")!=run["head_sha"]
        or type(data.get("source_run_id")) is not int
        or data["source_run_id"]!=run.get("id")):
        raise ValueError("GitHub workflow provenance mismatch")
    # Reject fallbacks to the historical, pre-expansion daily archive.
    if (data.get("input_source")!="espn_verified_13_league_upcoming_v1"
        or type(data.get("input_fixture_count")) is not int
        or not 0<=data["input_fixture_count"]<=300):
        raise ValueError("Expected fresh verified 13-league fixture source")
    counts=data.get("input_sport_counts")
    if (not isinstance(counts,dict)
        or set(counts)!={"soccer","hockey"}
        or any(type(x) is not int or x<0 for x in counts.values())
        or sum(counts.values())!=data["input_fixture_count"]):
        raise ValueError("Invalid soccer/NHL fixture counts")
    nhl_check=data.get("nhl_evaluation")
    if (not isinstance(nhl_check,dict)
        or nhl_check.get("status") not in
        ("evaluated_not_promoted","insufficient_nhl_history","insufficient_nhl_calibration","not_supplied")):
        raise ValueError("Invalid NHL research validation")
    exported=stamp(data.get("exported_at"))
    created=stamp(run.get("created_at"))
    issued=stamp(data.get("input_issued_at"))
    if (exported<created or exported>now or (now-exported).total_seconds()>48*3600
        or issued>exported or (exported-issued).total_seconds()>48*3600):
        raise ValueError("Stale or future-dated model handoff")
    from zoneinfo import ZoneInfo
    if (data.get("input_day")!=issued.astimezone(ZoneInfo("America/Chicago")).date().isoformat()
        or len(data.get("holdout_by_league",{}))!=13
        or set(data["holdout_by_league"])!=LEAGUES):
        raise ValueError("Incomplete league or source-day coverage")
    for league,metrics in data["holdout_by_league"].items():
        if (metrics.get("status") not in ("research_only_not_promoted","insufficient_model_evidence")
            or type(metrics.get("evaluated")) is not int or metrics["evaluated"]<0
            or metrics.get("calibrated") is not False or metrics.get("promoted") is not False):
            raise ValueError("Invalid research evidence")
        if metrics["status"]=="research_only_not_promoted":
            b=metrics.get("candidate_brier")
            if type(b) not in (int,float) or not math.isfinite(b) or not 0<=b<=1:
                raise ValueError("Invalid Brier evidence")
    forecasts=data.get("forecasts")
    if (not isinstance(forecasts,list) or len(forecasts)>300
        or len(forecasts)!=data["input_fixture_count"]):
        raise ValueError("Incomplete candidate fixture list or unmatched source count")
    seen=set()
    safe=[]
    for candidate in forecasts:
        event=candidate.get("id")
        key=candidate.get("league")
        status=candidate.get("status")
        is_nhl=(key=="nhl" and isinstance(event,str)
                and event.startswith("espn:hockey:nhl:"))
        is_soccer=(key in LEAGUES and isinstance(event,str)
                   and event.startswith("espn:soccer:"))
        if ((not is_nhl and not is_soccer)
            or event in seen or status not in ALLOWED_STATUS):
            raise ValueError("Untrusted candidate fixture")
        seen.add(event)
        item={"id":event,"league":key,"status":status,
              "sport":"hockey" if is_nhl else "soccer"}
        if status=="research_forecast_not_promoted":
            expected_model=("nhl_team_parity_regularized_platt_v1"
                            if is_nhl else data["model"])
            if (candidate.get("model")!=expected_model or
                candidate.get("calibrated") is not False or
                candidate.get("market_verified") is not False or
                candidate.get("qualified_bet") is not False):
                raise ValueError("Unapproved candidate forecast")
            if is_nhl:
                if nhl_check["status"]!="evaluated_not_promoted" or nhl_check.get("n_test",0)<20:
                    raise ValueError("NHL calibration evidence missing")
            else:
                evidence=data["holdout_by_league"][key]
                if (candidate.get("calibration_evaluated") is not True
                    or evidence.get("calibration_status")!="evaluated_not_promoted"
                    or evidence.get("calibration_n_test",0)<20):
                    raise ValueError("Soccer calibration evidence missing")
            even,odd=candidate.get("p_even"),candidate.get("p_odd")
            if (type(even) not in (int,float) or type(odd) not in (int,float)
                or not math.isfinite(even) or not math.isfinite(odd)
                or not 0<even<1 or abs(even+odd-1)>1e-6):
                raise ValueError("Invalid model probabilities")
            modeled=stamp(candidate.get("issued_at"))
            kickoff=stamp(candidate.get("kickoff_utc"))
            if modeled!=exported or modeled>=kickoff:
                raise ValueError("Post-kickoff or mismatched model issue time")
            side="EVEN" if even>=.5 else "ODD"
            if candidate.get("prediction")!=side:
                raise ValueError("Inconsistent EVEN/ODD classification")
            home,away=candidate.get("home"),candidate.get("away")
            if (not isinstance(home,str) or not home.strip()
                or not isinstance(away,str) or not away.strip() or home==away
                or len(home)>120 or len(away)>120):
                raise ValueError("Missing public source team names")
            item.update(p_even=round(even,6),p_odd=round(odd,6),
                        prediction=side,home=home,away=away,
                        model=expected_model,calibration_evaluated=True,
                        issued_at=modeled.isoformat(),kickoff_utc=kickoff.isoformat())
        else:
            if "p_even" in candidate or "p_odd" in candidate:
                raise ValueError("Unverified match supplied numeric predictions")
        safe.append(item)
    # Whitelist evidence fields explicitly: never copy private raw datasets,
    # feature vectors, secrets or hidden research fields to public GitHub.
    return {"schema_version":1,"source_run_id":run["id"],
        "source_commit":run["head_sha"],"source_repository":PRIVATE,
        "model":data["model"],"input_day":data["input_day"],
        "input_source":data["input_source"],
        "input_fixture_count":data["input_fixture_count"],
        "input_sport_counts":counts,
        "exported_at":exported.isoformat(),
        "status":"research_only_not_promoted",
        "calibrated":False,"markets_verified":False,"qualified_bets":0,
        "trades_placed":0,"production_enabled":False,
        "forecasts":safe,
        "holdout_evaluated":{k:x["evaluated"] for k,x in data["holdout_by_league"].items()}}

class _ArtifactRedirect(HTTPRedirectHandler):
    """Do not forward a private GitHub token to the artifact download host."""
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        origin=urlsplit(req.full_url)
        target=urlsplit(newurl)
        host=target.hostname or ""
        if target.scheme!="https" or target.username or target.password:
            raise ValueError("Unsafe artifact redirect protocol")
        if origin.hostname=="api.github.com":
            allowed=(host=="objects.githubusercontent.com"
                     or host.endswith(".blob.core.windows.net"))
            if not allowed:
                raise ValueError("Untrusted artifact redirect destination")
        elif host!=origin.hostname:
            raise ValueError("Unexpected second artifact redirect")
        next_request=super().redirect_request(req,fp,code,msg,headers,newurl)
        if next_request is None:
            return None
        if host!=origin.hostname:
            # The target has a signed URL. Reusing the GitHub Authorization
            # header on Azure can fail authentication or leak the PAT.
            sensitive={"authorization","x-github-api-version","accept"}
            for mapping in (next_request.headers,next_request.unredirected_hdrs):
                for key in list(mapping):
                    if key.lower() in sensitive:
                        del mapping[key]
        return next_request

def _get(url,token,*,opener=None,binary=False):
    parts=urlsplit(url)
    if (parts.scheme!="https" or parts.hostname!="api.github.com"
        or not parts.path.startswith("/repos/"+PRIVATE+"/actions/")):
        raise ValueError("Untrusted private repository API endpoint")
    opener=opener or build_opener(_ArtifactRedirect()).open
    req=Request(url,headers={
        "Authorization":"Bearer "+token,
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"StatRallyReadOnlyModelHandoff/1"})
    with opener(req,timeout=30) as response:
        body=response.read(4_000_001)
    if len(body)>4_000_000:
        raise ValueError("Oversized private model response")
    return body if binary else json.loads(body)

def retrieve(token,*,get=_get,now=None):
    if not token:
        raise ValueError("STATRALLY_MODELS_READ_TOKEN missing")
    run_payload=get(f"https://api.github.com/repos/{PRIVATE}/actions/workflows/{WORKFLOW}/runs?branch=main&status=success&per_page=30",token)
    runs=run_payload.get("workflow_runs",[])
    if not isinstance(runs,list):
        raise ValueError("GitHub model workflow inaccessible")
    now=now or datetime.now(timezone.utc)
    eligible=[r for r in runs if (r.get("status")=="completed"
              and r.get("conclusion")=="success"
              and r.get("head_branch")=="main"
              and r.get("event") in ("schedule","workflow_dispatch","push")
              and 0<=(now-stamp(r["created_at"])).total_seconds()<=48*3600)]
    if not eligible:
        raise ValueError("No fresh successful private model handoff")
    run=max(eligible,key=lambda x:x["created_at"])
    artifacts=get(f"https://api.github.com/repos/{PRIVATE}/actions/runs/{run['id']}/artifacts?per_page=100",token)
    found=[x for x in artifacts.get("artifacts",[])
           if x.get("name")==f"statrally-model-handoff-{run['id']}"
           and x.get("expired") is False]
    if len(found)!=1:
        raise ValueError("No exact verified private handoff artifact")
    raw=get(f"https://api.github.com/repos/{PRIVATE}/actions/artifacts/{found[0]['id']}/zip",token,binary=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as package:
        if package.namelist()!=["model-handoff.json"]:
            raise ValueError("Untrusted handoff archive contents")
        member=package.getinfo("model-handoff.json")
        if member.file_size>500_000:
            raise ValueError("Untrusted zip expansion")
        data=json.loads(package.read(member))
    return validate(data,run,now=now)

def record(public_repo,projection,*,call=github):
    title=TITLE+projection["input_day"]+" | "+str(projection["source_run_id"])
    body=PREFIX+json.dumps(projection,sort_keys=True,separators=(",",":"))
    if len(body)>60_000:
        raise ValueError("Oversized public research evidence")
    for page in range(1,11):
        items=call("GET",public_repo,f"/issues?state=all&per_page=100&page={page}")
        if not isinstance(items,list):
            raise ValueError("Unable to verify prior handoff state")
        matches=[x for x in items if x.get("title")==title and "pull_request" not in x]
        if len(matches)>1:
            raise ValueError("Duplicate model handoff")
        if matches:
            previous=matches[0]
            if previous.get("user",{}).get("login")!=BOT or previous.get("body")!=body:
                raise ValueError("Conflicting model handoff")
            return {"status":"already_recorded","issue_number":previous["number"]}
        if len(items)<100:break
    else:
        raise ValueError("Model handoff pagination incomplete")
    created=call("POST",public_repo,"/issues",{"title":title,"body":body})
    if type(created.get("number")) is not int:
        raise ValueError("Unconfirmed research evidence archive")
    return {"status":"recorded","issue_number":created["number"]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="out/model-handoff-evidence.json")
    args=parser.parse_args()
    result=retrieve(os.environ.get("STATRALLY_MODELS_READ_TOKEN",""))
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,sort_keys=True)+"\n",encoding="utf-8")
    archived=record(os.environ["GITHUB_REPOSITORY"],result)
    print("MODEL_HANDOFF_CONSUMED="+json.dumps({
        "issue_number":archived["issue_number"],"status":archived["status"],
        "source_run_id":result["source_run_id"],
        "candidate_forecasts":sum(x["status"]=="research_forecast_not_promoted"
                                 for x in result["forecasts"]),
        "qualified_bets":0,"production_enabled":False},sort_keys=True))

if __name__=="__main__":
    main()
