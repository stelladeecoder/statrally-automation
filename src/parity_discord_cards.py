"""Source-verified Even/Odd Discord presentation contracts.

Only the watchlist is currently delivered. Picks and results renderers are
strict, reusable UI contracts; their Discord delivery pipelines remain gated.
"""
import math
from datetime import datetime,timezone
from parity_research import LEAGUES,parse_time

BLUE=0x3498db
GREEN=0x2ecc71
RED=0xe74c3c
MAX_SELECTIONS=15

def _sport(value):
    if value not in ("soccer","hockey"):
        raise ValueError("Unsupported sport")
    return "⚽ SOCCER" if value=="soccer" else "🏒 NHL"

def _team(row):
    if not all(isinstance(row.get(k),str) and row[k].strip() for k in ("home","away","id")):
        raise ValueError("Unverified match identity")
    if row["league"] not in LEAGUES or LEAGUES[row["league"]][0]!=row["sport"]:
        raise ValueError("Sport/competition mismatch")
    return row["away"]+" @ "+row["home"]

def _chance(value):
    if type(value) not in (float,int) or not math.isfinite(value) or not 0<value<1:
        raise ValueError("Invalid evidence-backed probability")
    return value

def picks_preview(sport,day,candidates,*,now=None):
    """Render ONLY independently approved/qualified selections, never baselines.

    This is a presentation primitive; it does not send any Discord post.
    """
    _sport(sport)
    now=now or datetime.now(timezone.utc)
    if not isinstance(candidates,list) or not 0<len(candidates)<=MAX_SELECTIONS:
        raise ValueError("No approved candidates available")
    seen=set()
    body=[f"**{len(candidates)} VERIFIED SELECTIONS**"]
    for row in candidates:
        if row.get("sport")!=sport:
            raise ValueError("Cross-sport candidate")
        name=_team(row)
        if row["id"] in seen:raise ValueError("Duplicate fixture selection")
        seen.add(row["id"])
        if any(row.get(k) is not True for k in
               ("model_promoted","model_calibrated","market_verified","qualified_bet")):
            raise ValueError("Unapproved or uncalibrated selection")
        if row.get("selection") not in ("EVEN","ODD"):
            raise ValueError("Invalid side")
        even=_chance(row.get("p_even"))
        odd=_chance(row.get("p_odd"))
        if abs(even+odd-1)>1e-6:raise ValueError("Probability mass mismatch")
        market=row.get("market_odds_decimal")
        if type(market) not in (float,int) or not math.isfinite(market) or market<=1:
            raise ValueError("Missing verified market odds")
        kick=parse_time(row["kickoff_utc"])
        priced=parse_time(row.get("price_as_of_utc"))
        if kick<=now or priced>now or priced>=kick:
            raise ValueError("Post-kickoff or future price")
        if not row.get("market_id") or not row.get("settlement_verified"):
            raise ValueError("Unverified market or settlement")
        side=row["selection"]
        body.extend(["",f"**{name}** • <t:{int(kick.timestamp())}:t>",
                     f"**{side}**  ·  Model {(_chance(even if side=='EVEN' else odd)):.1%}  ·  Market {market:.2f} decimal"])
    return {"embeds":[{"title":_sport(sport)+" | EVEN/ODD PICKS · "+str(day),
         "description":"\n".join(body),"color":BLUE,
         "footer":{"text":"Only source-verified, validated, market-qualified pregame picks"}}],
         "allowed_mentions":{"parse":[]}}

def result_card(row):
    """Render one verified parity prediction result, not a financial P/L."""
    sport=row.get("sport")
    sport_label=_sport(sport)
    name=_team(row)
    if (row.get("grade_status")!="graded" or row.get("final_verified") is not True
        or row.get("original_forecast_saved") is not True
        or row.get("actual") not in ("EVEN","ODD")
        or row.get("predicted") not in ("EVEN","ODD")
        or type(row.get("total")) is not int or row["total"]<0
        or row["actual"]!=("EVEN" if row["total"]%2==0 else "ODD")):
        raise ValueError("Unverified result or unsupported final")
    correct=row["predicted"]==row["actual"]
    return {"embeds":[{"title":sport_label+" | VERIFIED RESULT",
         "description":f"**{name}**\nFinal combined total: **{row['total']}**\n"
                       f"Original research forecast: **{row['predicted']}**\n"
                       f"Verified outcome: **{row['actual']}**\n"
                       +("✅ Correct forecast" if correct else "❌ Incorrect forecast"),
         "color":GREEN if correct else RED,
         "footer":{"text":"Verified final-score research result • Not a settled wager"}}],
         "allowed_mentions":{"parse":[]}}
