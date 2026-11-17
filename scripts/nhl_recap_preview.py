"""Synthetic recap preview; never writes ledger or production reservations."""
import json
import os
from nhl_paper_recap_scheduler import publish_recap
from nhl_moneyline_ledger_delivery import send

def main():
    live = os.environ.get("RECAP_TEST_SEND") == "true"
    data = {"scheduled_slate_games": 3, "settled_slate_games": 2,
            "settled_contracts": 2, "trades_placed": 3, "wins": 1,
            "losses": 1, "pending": 1, "settlement_dates": ["2026-11-17"],
            "settled_cost": "1.10", "clv_sum": "0.04",
            "post_fee_paper_pnl_dollars": "-0.10"}
    for kind in ("daily", "weekly", "monthly"):
        captured = []
        def fake_api(method, repo, path, payload=None, **kwargs):
            if method == "GET":
                return []
            return {"number": 1}
        def preview_sender(webhook, payload):
            payload["embeds"][0]["title"] = "[TEST / PAPER] " + payload["embeds"][0]["title"]
            payload["embeds"][0]["description"] = "SYNTHETIC FIXTURE — NOT REAL PERFORMANCE\n" + payload["embeds"][0]["description"]
            captured.append(payload)
            return send(webhook, payload) if live else "123"
        key = "STATRALLY_NHL_" + kind.upper() + "_RECAP_WEBHOOK"
        if not live:
            os.environ[key] = "offline"
        result = publish_recap(kind, "SYNTHETIC", data, call=fake_api, sender=preview_sender)
        if result["status"] != "CONFIRMED" or len(captured) != 1:
            raise RuntimeError("Preview delivery unconfirmed: " + kind)
        assert "[TEST / PAPER]" in captured[0]["embeds"][0]["title"]
        print(json.dumps({"kind": kind, "mode": "webhook" if live else "offline", "confirmed": True}))
if __name__ == "__main__":
    main()
