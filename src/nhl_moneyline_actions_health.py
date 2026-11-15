"""Read the private NHL per-day aggregated health artifact with Actions:read.

The existing STATRALLY_MODELS_READ_TOKEN cannot read private GitHub Issues
(verified 403), but can read the private Actions artifacts API (verified 200).
Only a validated, nonsensitive aggregated JSON crosses this boundary.
"""
import io
import json
import zipfile
from datetime import date
from urllib.request import Request, urlopen
from urllib.parse import quote

REPO="stelladeecoder/statrally-even-odd-models"
ROOT="https://api.github.com/repos/"+REPO
SCHEMA="statrally-nhl-paper-health-summary-v1"
PREFIX="nhl-moneyline-health-"
FILE="nhl-moneyline-health.json"

def read(url,token,*,opener=urlopen,binary=False):
    if not token:raise ValueError("Private-model Actions read token missing")
    if not url.startswith(ROOT+"/actions/"):
        raise ValueError("Only private model Actions GET endpoints allowed")
    request=Request(url,method="GET",headers={
        "Authorization":"Bearer "+token,
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28"})
    with opener(request,timeout=30) as r:
        value=r.read()
    return value if binary else json.loads(value)

def load(day,*,token,request=read):
    day=str(date.fromisoformat(str(day)))
    for page in range(1,6):
        listing=request(ROOT+f"/actions/artifacts?per_page=100&page={page}",token)
        artifacts=listing.get("artifacts",[])
        if not isinstance(artifacts,list):raise ValueError("Invalid private Actions listing")
        for item in artifacts:
            if not str(item.get("name","")).startswith(PREFIX) or item.get("expired"):
                continue
            aid=item.get("id")
            if type(aid)!=int:
                raise ValueError("Invalid private artifact ID")
            raw=request(ROOT+f"/actions/artifacts/{aid}/zip",token,binary=True)
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries=[name for name in archive.namelist()
                         if name.split("/")[-1]==FILE]
                if len(entries)!=1:
                    raise ValueError("Private health artifact has no unique summary")
                report=json.loads(archive.read(entries[0]))
            if report.get("date_central")!=day:
                continue
            validate(report,day)
            return report
        if len(artifacts)<100:break
    return None

def validate(report,day):
    if (report.get("schema")!=SCHEMA
        or report.get("date_central")!=str(day)
        or report.get("source_repository")!=REPO
        or report.get("paper_only") is not True
        or report.get("orders_placed")!=0
        or report.get("status") not in ("verified_receipts","no_daily_receipts")):
        raise ValueError("Untrusted private NHL health summary")
    keys=("poll_runs_observed","scheduled_polls_observed",
          "scheduled_polls_expected","unconfirmed_scheduled_polls",
          "entry_hits","entry_misses_observed","close_hits",
          "close_misses_observed","kalshi_api_skips","low_liquidity_skips",
          "model_source_errors","identity_skips","poll_failures")
    for key in keys:
        if type(report.get(key)) is not int or report[key]<0:
            raise ValueError("Invalid private NHL health count "+key)
    if report["poll_runs_observed"]<report["scheduled_polls_observed"]:
        raise ValueError("More scheduled than observed runs")
    if report["status"]=="no_daily_receipts" and report["poll_runs_observed"]!=0:
        raise ValueError("Missing-receipts status conflicts with observed count")
    return report

def lines_for_day(day,*,token,loader=load):
    if not token:
        return ["NHL Moneyline [PAPER] health: PRIVATE ACTIONS READ TOKEN MISSING."]
    try:
        r=loader(day,token=token)
    except Exception as exc:
        return [f"NHL Moneyline [PAPER] health: ARTIFACT READ ERROR ({type(exc).__name__}); snapshot receipts unverified."]
    if r is None:
        return ["NHL Moneyline [PAPER] health: daily private summary artifact unavailable; snapshot hits/misses UNKNOWN."]
    text=[
        f"NHL Moneyline [PAPER] 5-min polls: {r['poll_runs_observed']}/{r['scheduled_polls_expected']} expected; unconfirmed slots: {r['unconfirmed_scheduled_polls']}",
        f"Entry snapshot contract hits/misses: {r['entry_hits']}/{r['entry_misses_observed']}",
        f"Pre-puck closing snapshot contract hits/misses: {r['close_hits']}/{r['close_misses_observed']}",
        f"Kalshi/API skips: {r['kalshi_api_skips']} | low-liquidity skips: {r['low_liquidity_skips']}",
        f"Model/source errors: {r['model_source_errors']} | identity skips: {r['identity_skips']} | poll failures: {r['poll_failures']}",
        "No backfilled quotes. Misses count observed attempts; unconfirmed poll slots may conceal additional misses."
    ]
    return text
