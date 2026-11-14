"""One-time, receipt-confirmed NHL Discord watchlist test.

No model predictions, game picks, prices, trading, or spam retries.
"""
import json
import os
from datetime import datetime, timezone
from parity_discord import github, discord_send, reservation, RESERVATION
from verify_nhl_watchlist_webhook import verify

TITLE="StatRally NHL watchlist webhook test | 2026-11-14"
EXPECTED_CHANNEL_ID="1561051260877144114"

def send_test(webhook,repo,*,call=github,sender=discord_send,verifier=verify):
    if not webhook:
        raise ValueError("Dedicated NHL watchlist webhook missing")
    check=verifier(webhook,"")
    if (check.get("verified") is not True or
        str(check.get("channel_id",""))!=EXPECTED_CHANNEL_ID):
        raise ValueError("NHL webhook channel changed or was not verified")
    # Reserve once BEFORE posting, to prevent duplicate tests on retries.
    checkpoint=reservation(repo,TITLE,call=call)
    if checkpoint is None:
        print("NHL_WATCHLIST_TEST_ALREADY_RESERVED_NO_RESEND")
        return {"status":"previously_reserved","sent":False}
    payload={"content":(
        "🏒 **StatRally NHL Watchlist | Connection Test**\n"
        "✅ NHL channel webhook test message.\n"
        "This is a TEST ONLY. No game predictions, betting picks, results, "
        "or real-money trades were generated.\n"
        "Future NHL Even/Odd research watchlists are intended for this channel."
    ),"allowed_mentions":{"parse":[]}}
    message_id=sender(webhook,payload)
    updated=call("PATCH",repo,f"/issues/{checkpoint}",{
        "state":"closed",
        "body":RESERVATION+json.dumps({
            "status":"confirmed","key":TITLE,
            "message_id":message_id,"channel_id":EXPECTED_CHANNEL_ID
        },sort_keys=True)
    })
    if updated.get("number")!=checkpoint:
        raise ValueError("Test delivered but GitHub receipt could not be persisted")
    return {"status":"confirmed","sent":True,
            "message_id":message_id,"channel_id":EXPECTED_CHANNEL_ID}

if __name__=="__main__":
    result=send_test(os.environ.get("STATRALLY_NHL_WATCHLIST_WEBHOOK",""),
                     os.environ["GITHUB_REPOSITORY"])
    print("NHL_WATCHLIST_TEST="+json.dumps(result,sort_keys=True))
