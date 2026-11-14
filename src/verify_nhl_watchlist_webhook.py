"""Read-only verification of the NHL watchlist Discord webhook.

Does not send messages or expose the webhook URL/token.
A valid Discord webhook may still point to an unexpected channel;
the owner must verify the destination in Discord.
"""
import json
import os
from urllib.request import Request,urlopen
from urllib.parse import urlsplit

def verify(hockey,soccer,*,opener=urlopen):
    if not hockey:
        return {"status":"missing","verified":False,"message_sent":False}
    endpoint=urlsplit(hockey)
    if (endpoint.scheme!="https" or endpoint.hostname not in ("discord.com","discordapp.com")
        or not endpoint.path.startswith("/api/webhooks/") or endpoint.username or endpoint.password):
        raise ValueError("Invalid NHL webhook origin")
    if soccer and hockey.strip()==soccer.strip():
        raise ValueError("NHL webhook is identical to soccer's webhook")
    request=Request(hockey,headers={"Accept":"application/json",
                                    "User-Agent":"StatRally-NHL-Watchlist-Verify/1"})
    with opener(request,timeout=15) as response:
        if response.status!=200:
            raise ValueError("Discord webhook endpoint did not confirm")
        payload=json.load(response)
    if (not isinstance(payload,dict) or not str(payload.get("id","")).isdigit()
        or not str(payload.get("channel_id","")).isdigit()):
        raise ValueError("Discord webhook channel identity not confirmed")
    return {"status":"webhook_valid","verified":True,
            "channel_id":str(payload["channel_id"]),
            "message_sent":False}

if __name__=="__main__":
    from urllib.error import HTTPError,URLError
    try:
        result=verify(os.environ.get("STATRALLY_NHL_WATCHLIST_WEBHOOK",""),
            os.environ.get("STATRALLY_PARITY_SOCCER_WEBHOOK") or
            os.environ.get("STATRALLY_PARITY_DISCORD_WEBHOOK",""))
        print("NHL_WATCHLIST_WEBHOOK_HEALTH="+json.dumps(result,sort_keys=True))
        if not result["verified"]:
            raise SystemExit(1)
    except (ValueError,HTTPError,URLError,TimeoutError) as exc:
        print("NHL_WATCHLIST_WEBHOOK_HEALTH="+json.dumps({
            "status":"verification_failed","verified":False,
            "error_type":type(exc).__name__,"message_sent":False}))
        raise SystemExit(1)
