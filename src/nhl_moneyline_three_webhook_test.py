"""One-time [TEST / PAPER] connectivity check of all three existing NHL webhooks.

No real fixtures, prices, predictions, settlements or trade actions.
Only explicitly named existing NHL webhooks. Never prints webhook URLs/tokens.
"""
import json
import os
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from parity_discord import discord_send

SECRETS = {
    "watchlist": "STATRALLY_NHL_WATCHLIST_WEBHOOK",
    "picks": "STATRALLY_NHL_PICKS_WEBHOOK",
    "results": "STATRALLY_NHL_RESULTS_WEBHOOK",
}


def verify(webhook, *, opener=urlopen):
    parts=urlsplit(webhook)
    if (parts.scheme!="https" or parts.hostname not in ("discord.com","discordapp.com")
        or not parts.path.startswith("/api/webhooks/") or parts.username or parts.password):
        raise ValueError("Invalid Discord webhook host or path")
    req=Request(webhook,headers={"Accept":"application/json",
                                  "User-Agent":"StatRallyNHLMoneylinePaperTest/1"},method="GET")
    with opener(req,timeout=15) as response:
        if response.status != 200:
            raise ValueError("Webhook verification failed")
        obj=json.load(response)
    if not str(obj.get("id","")).isdigit() or not str(obj.get("channel_id","")).isdigit():
        raise ValueError("Webhook channel identity missing")
    return str(obj["channel_id"])


def check(environ, *, verifier=verify, sender=discord_send):
    urls={name:environ.get(secret,"").strip() for name,secret in SECRETS.items()}
    if not all(urls.values()):
        raise ValueError("At least one NHL webhook secret is missing")
    if len(set(urls.values()))!=3:
        raise ValueError("NHL webhook URLs must be distinct")
    channel_ids={name:verifier(url) for name,url in urls.items()}
    if len(set(channel_ids.values()))!=3:
        raise ValueError("All three NHL webhooks must point to different channels")
    stamp=datetime.now(timezone.utc).isoformat()
    outcomes={}
    for name,url in urls.items():
        payload={"content":(
            f"[TEST / PAPER] StatRally NHL Moneyline webhook connection check: "
            f"#{'nhl-'+name} | {stamp}\n"
            "This is a connectivity-only test. NO games, odds, models, "
            "bets, positions, CLV, settlements or returns are represented. "
            "Live order execution is disabled. Scheduled paper trading is NOT active."
        ),"allowed_mentions":{"parse":[]}}
        mid=sender(url,payload)
        if not str(mid).isdigit():
            raise ValueError("Discord did not confirm a message receipt")
        outcomes[name]={"channel_id":channel_ids[name],"message_id":str(mid),
                        "verified":True,"paper_only":True}
    return {"status":"confirmed","sent_at_utc":stamp,"channels":outcomes,
            "message_count":len(outcomes),"orders_placed":0}


if __name__=="__main__":
    try:
        result=check(os.environ)
        print("NHL_MONEYLINE_THREE_CHANNEL_TEST="+json.dumps(result,sort_keys=True))
    except Exception as exc:
        # Never print sensitive exception text, which can include webhook URLs.
        print("NHL_MONEYLINE_THREE_CHANNEL_TEST="+json.dumps({
            "status":"FAILED","error_type":type(exc).__name__,"note":"Inspect safe configuration privately"}))
        raise SystemExit(1)
