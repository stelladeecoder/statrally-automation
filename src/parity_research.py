"""Read-only, source-verified soccer/NHL Even/Odd research-only beta.

ESPN scoreboard source is public-facing but unofficial and may be withdrawn.
No contract availability, prices, fees or profitable edge has been validated.
"""
import argparse
import json
import math
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo

CENTRAL=ZoneInfo("America/Chicago")
LEAGUES={
  "soccer_epl":("soccer","eng.1","Premier League","men","90_minutes"),
  "soccer_laliga":("soccer","esp.1","LaLiga","men","90_minutes"),
  "soccer_bundesliga":("soccer","ger.1","Bundesliga","men","90_minutes"),
  "soccer_serie_a":("soccer","ita.1","Serie A","men","90_minutes"),
  "soccer_mls":("soccer","usa.1","MLS","men","90_minutes"),
  "soccer_ligue_1":("soccer","fra.1","Ligue 1","men","90_minutes"),
  "soccer_eredivisie":("soccer","ned.1","Eredivisie","men","90_minutes"),
  "soccer_liga_portugal":("soccer","por.1","Liga Portugal","men","90_minutes"),
  "soccer_brasileirao":("soccer","bra.1","Brasileirão Série A","men","90_minutes"),
  "soccer_liga_mx":("soccer","mex.1","Liga MX","men","90_minutes"),
  "soccer_primera_lpf":("soccer","arg.1","Argentine Primera División","men","90_minutes"),
  "soccer_champions_league":("soccer","uefa.champions","UEFA Champions League","men","90_minutes"),
  "soccer_europa_league":("soccer","uefa.europa","UEFA Europa League","men","90_minutes"),
  "soccer_nwsl":("soccer","usa.nwsl","NWSL","women","90_minutes"),
  "soccer_uwcl":("soccer","uefa.wchampions","Women's Champions League","women","90_minutes"),
  "nhl":("hockey","nhl","NHL","men","full_game_including_shootout_score"),
}
SOCCER_FINAL="STATUS_FULL_TIME"
NHL_FINAL="STATUS_FINAL"

def parse_time(value):
    if not isinstance(value,str):
        raise ValueError("Timestamp must be a string")
    time=datetime.fromisoformat(value.replace("Z","+00:00"))
    if time.tzinfo is None:
        raise ValueError("Timestamp is missing timezone")
    return time.astimezone(timezone.utc)

def fetch_scoreboard(key,start,end):
    sport,code,*_=LEAGUES[key]
    if end<start:
        raise ValueError("Invalid scoreboard date range")
    if start!=end:
        raise ValueError("ESPN requires an individually requested scoreboard date")
    date_arg=f"{start:%Y%m%d}"
    url=f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{code}/scoreboard?dates={date_arg}&limit=500"
    # Retry bounded transient TLS/network or server failures, not bad requests.
    for attempt in range(3):
        try:
            with urlopen(Request(url,headers={"Accept":"application/json","User-Agent":"StatRallyParityResearch/0.1"}),timeout=18) as response:
                payload=json.load(response)
            return parse_scoreboard(key,payload,url)
        except (URLError,TimeoutError,OSError) as exc:
            if isinstance(exc,HTTPError) and exc.code not in (429,500,502,503,504):
                raise RuntimeError(f"Permanent scoreboard error {key} {date_arg}: HTTP {exc.code}") from exc
            if attempt==2:
                raise RuntimeError(f"Scoreboard failed {key} {date_arg} after 3 attempts: {type(exc).__name__} {getattr(exc,'code','')}") from exc
            time.sleep(1+attempt)

def parse_scoreboard(key,payload,source_url):
    """Verify ESPN event and score identities; quarantine incomplete scores."""
    if key not in LEAGUES or not isinstance(payload,dict) or not isinstance(payload.get("events"),list):
        raise ValueError("ESPN scoreboard missing events field")
    sport,code,label,category,period=LEAGUES[key]
    records=[]
    ids=set()
    for event in payload["events"]:
        if not isinstance(event,dict) or not str(event.get("id","")).isdigit():
            raise ValueError("Invalid event identity")
        event_id=str(event["id"])
        if event_id in ids:
            raise ValueError("Duplicate ESPN event identity")
        ids.add(event_id)
        kickoff=parse_time(event["date"])
        comp=event.get("competitions")
        if not isinstance(comp,list) or len(comp)!=1:
            raise ValueError("Ambiguous event competition")
        sides=comp[0].get("competitors")
        if not isinstance(sides,list) or len(sides)!=2:
            raise ValueError("Invalid match sides")
        home=[x for x in sides if x.get("homeAway")=="home"]
        away=[x for x in sides if x.get("homeAway")=="away"]
        if len(home)!=1 or len(away)!=1:
            raise ValueError("Unverified home and away roles")
        h,a=home[0],away[0]
        h_id=str(h.get("team",{}).get("id",""))
        a_id=str(a.get("team",{}).get("id",""))
        if not h_id.isdigit() or not a_id.isdigit() or h_id==a_id:
            raise ValueError("Unverified team identities")
        h_name=h.get("team",{}).get("displayName")
        a_name=a.get("team",{}).get("displayName")
        if not all(isinstance(x,str) and x.strip() for x in (h_name,a_name)):
            raise ValueError("Missing team name")
        status=event.get("status",{}).get("type",{})
        if not isinstance(status,dict):
            raise ValueError("Missing event status")
        state=status.get("state")
        completed=status.get("completed")
        name=status.get("name")
        if type(completed) is not bool:
            raise ValueError("Unverified completion status")
        record={"id":f"espn:{sport}:{code}:{event_id}","sport":sport,"league":key,
                "competition_name":label,"category":category,"settlement_basis":period,
                "home":h_name,"away":a_name,"home_team_id":h_id,"away_team_id":a_id,
                "kickoff_utc":kickoff.isoformat(),"source":source_url,
                "status":"unconfirmed","score_total":None,"parity":None}
        if completed:
            if name not in (SOCCER_FINAL if sport=="soccer" else NHL_FINAL,):
                # Exclude aggregate/two-leg and nonstandard results.
                record["status"]="unsupported_final"
            else:
                scores=[h.get("score"),a.get("score")]
                if any(type(s) not in (str,int) or not str(s).isdigit() for s in scores):
                    raise ValueError("Completed game missing integer scores")
                total=sum(int(s) for s in scores)
                record.update(status="graded",score_total=total,
                              parity="EVEN" if total%2==0 else "ODD")
        elif state=="pre" and name in ("STATUS_SCHEDULED","STATUS_PRE_GAME","STATUS_PREVIEW"):
            record["status"]="pregame"
        else:
            record["status"]="in_progress_or_unverified"
        records.append(record)
    return records

def probability(fixture,history,now,*,minimum=12):
    """Smoothed per-competition parity prevalence. Not a proven betting edge."""
    as_of=parse_time(now)
    kickoff=parse_time(fixture["kickoff_utc"])
    if as_of>=kickoff:
        raise ValueError("No post-kickoff forecast")
    cutoff=min(as_of.date(),kickoff.date())
    previous=[x for x in history if x["league"]==fixture["league"]
              and x["status"]=="graded"
              and parse_time(x["kickoff_utc"]).date()<cutoff]
    if len({x["id"] for x in previous})!=len(previous):
        raise ValueError("Duplicate research history")
    if len(previous)<minimum:
        return {"status":"insufficient_history","sample_size":len(previous),
                "minimum":minimum,"qualified_bet":False}
    even=sum(x["parity"]=="EVEN" for x in previous)
    p_even=(even+10)/(len(previous)+20)
    return {"status":"research_prediction","method":"league_beta_10_10_baseline_v1",
            "p_even":round(p_even,6),"p_odd":round(1-p_even,6),
            "sample_size":len(previous),"calibrated":False,
            "market_verified":False,"qualified_bet":False,
            "as_of_utc":as_of.isoformat()}

def backtest(history,*,minimum=12):
    """Walk-forward without same-calendar-day outcome leakage."""
    ordered=sorted((x for x in history if x["status"]=="graded"),
                   key=lambda r:(r["kickoff_utc"],r["id"]))
    predictions=[]
    for event in ordered:
        cutoff=parse_time(event["kickoff_utc"]).date()
        prior=[r for r in ordered if r["league"]==event["league"]
               and parse_time(r["kickoff_utc"]).date()<cutoff]
        if len(prior)<minimum:
            continue
        even=sum(x["parity"]=="EVEN" for x in prior)
        p=(even+10)/(len(prior)+20)
        actual=int(event["parity"]=="EVEN")
        predictions.append((p,actual))
    if not predictions:
        return {"status":"insufficient_evaluated_history","n":0}
    n=len(predictions)
    return {"status":"research_only","n":n,
        "accuracy":round(sum((p>=.5)==bool(y) for p,y in predictions)/n,6),
        "even_only_accuracy":round(sum(y for _,y in predictions)/n,6),
        "brier":round(sum((p-y)**2 for p,y in predictions)/n,6),
        "log_loss":round(-sum(y*math.log(p)+(1-y)*math.log(1-p) for p,y in predictions)/n,6)}

def build_report(*,now=None,history_days=35,fetch=fetch_scoreboard,keys=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None or not 14<=history_days<=90:
        raise ValueError("Timezone-aware now and 14–90 history days required")
    today=now.astimezone(CENTRAL).date()
    end=now.date()-timedelta(days=1)
    start=end-timedelta(days=history_days-1)
    keys=tuple(LEAGUES if keys is None else keys)
    if not keys or any(key not in LEAGUES for key in keys) or len(keys)!=len(set(keys)):
        raise ValueError("Unknown or repeated competition selection")
    snapshots=[]
    all_ids=set()
    for key in keys:
        historical=[]
        cursor=start
        while cursor<=end:
            historical.extend(fetch(key,cursor,cursor))
            cursor+=timedelta(days=1)
        if len({r["id"] for r in historical})!=len(historical):
            raise ValueError("Overlapping ESPN historical event identities")
        # Only verified historical finals before the UTC day are eligible.
        verified=[x for x in historical if x["status"]=="graded"
                  and parse_time(x["kickoff_utc"]).date()<now.date()]
        if any(x["id"] in all_ids for x in verified):
            raise ValueError("Duplicate multi-competition ID")
        all_ids.update(x["id"] for x in verified)
        # Schedule uses calendar days surrounding Central today, not UTC-only today.
        today_rows=[]
        for day in (today-timedelta(days=1),today,today+timedelta(days=1)):
            today_rows.extend(fetch(key,day,day))
        fixtures=[]
        seen_fixtures=set()
        for item in today_rows:
            kickoff=parse_time(item["kickoff_utc"])
            if kickoff.astimezone(CENTRAL).date()!=today or item["status"]!="pregame" or kickoff<=now:
                continue
            if item["id"] in seen_fixtures:
                continue
            seen_fixtures.add(item["id"])
            fixtures.append({"id":item["id"],"home":item["home"],"away":item["away"],
                "home_team_id":item["home_team_id"],"away_team_id":item["away_team_id"],
                "kickoff_utc":item["kickoff_utc"],
                "forecast":probability(item,verified,now.isoformat())})
        fixtures.sort(key=lambda r:(r["kickoff_utc"],r["id"]))
        snapshots.append({"league":key,"competition_name":LEAGUES[key][2],
            "category":LEAGUES[key][3],"settlement_basis":LEAGUES[key][4],
            "historical_games":len(verified),"historical_even":sum(r["parity"]=="EVEN" for r in verified),
            "historical_odd":sum(r["parity"]=="ODD" for r in verified),
            "backtest":backtest(verified),"fixtures":fixtures,
            "pregame_count":len(fixtures),"schedule_source_verified":True})
    return {"schema_version":1,"market":"TOTAL_SCORE_PARITY",
        "status":"research_only","day_central":today.isoformat(),
        "generated_at":now.astimezone(timezone.utc).isoformat(),
        "history_days":history_days,"sports":["soccer","hockey"],
        "competitions":snapshots,"markets_verified":False,"prices_verified":False,
        "models_promoted":False,"qualified_bets":0,"trades_placed":0,
        "discord_delivery_verified":False}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--history-days",type=int,default=35)
    parser.add_argument("--leagues",default=",".join(LEAGUES))
    parser.add_argument("--output",default="out/statrally-parity-research.json")
    args=parser.parse_args()
    report=build_report(history_days=args.history_days,
                        keys=args.leagues.split(","))
    target=Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("STATRALLY_PARITY_SCAN="+json.dumps({
        "date":report["day_central"],"leagues":len(report["competitions"]),
        "sports":report["sports"],
        "historical_games":sum(x["historical_games"] for x in report["competitions"]),
        "upcoming":sum(x["pregame_count"] for x in report["competitions"]),
        "research_forecasts":sum(f["forecast"]["status"]=="research_prediction"
            for x in report["competitions"] for f in x["fixtures"]),
        "qualified_bets":0,"trades_placed":0},sort_keys=True))
if __name__=="__main__":
    main()
