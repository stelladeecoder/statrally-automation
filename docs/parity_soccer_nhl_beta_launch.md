# StatRally Even/Odd dual-sport research beta launch

**Launch target:** 14 November 2026. **Research-only**: no verified sportsbook
offer, executable quote, profitable edge, premium subscriptions, or wagers.

## Two sports under one StatRally brand

- **Soccer:** verified ESPN 90-minute final-score goals parity, with
  separate men's Premier League, LaLiga, Bundesliga, Serie A, MLS,
  women's NWSL and Women's Champions League competition coverage.
- **NHL:** verified ESPN final scoreboard total-goals parity, explicitly
  including overtime/shootout-final scoreboard outcome where recorded.
  This is **not interchangeable** with an NHL regulation-only market.
- Every competition is independently counted; unverified/missing sources
  cause workflow failure instead of fabricated predictions.
- Research probabilities use a Beta(10,10) competition-wide historical
  EVEN prevalence baseline, no same-day result leakage. Both sides
  always sum to one. Predictions are uncalibrated, with zero approved picks.
- Historical walk-forward metrics compare predictive classification and
  Brier/log loss to an always-even reference; small windows may be
  insufficient to evaluate.
- All eligible verified pregame games are retained in the workflow
  audit artifact. Discord shows up to four per competition (message
  size limits) and labels additional fixtures; no "Top 3" limit.
- Run at **09:15 UTC daily** (03:15 CST / 04:15 CDT), also on merge to main
  and manual workflow_dispatch. GitHub scheduling is best-effort.
- Main-branch delivery uses a new `STATRALLY_PARITY_DISCORD_WEBHOOK`
  when configured, otherwise existing `STATRALLY_DISCORD_WEBHOOK`
  if present. Delivery is a **single research-only status message** to
  the currently configured destination, never a betting-picks channel
  by implication. A missing webhook produces only a dry run.
- GitHub Issue reservations by Central calendar day prevent blind retry
  after uncertain Discord sends. No resend after a reserved or
  ambiguous delivery.

## What is not proven

The ESPN endpoints are publicly reachable, but **not guaranteed stable or
licensed for redistribution**. The prediction baseline has no verified
betting advantage. The 21-day research window is not a full-season
multi-year holdout. No Polymarket US, BetMGM or other sportsbook
**specific Even/Odd contract** has been located and matched to an
actual fixture at executable pregame odds. The live workflow itself
must finish successfully and obtain a Discord receipt before anyone
can claim a delivered launch.

## Rules that must be preserved

Soccer bookmaker references:
https://help.bet365.com/s/en-us/sportsrules/soccer/goalscoring-markets
(0-0 is EVEN; normal-time scope must be checked).

NHL **different market scopes**, not equivalent:
https://sportsbook.fanatics.com/legal/in/house-rules
(final totals may include shootout credited scoreboard goal).
https://www.kokwelresorts.com/wp-content/uploads/2026/02/2602-Caesars-Sportsbook-Rule-Book-Web.pdf
(60-minute odd/even expressly excludes overtime and shootout).

The generic `nhl` parity observation follows reported *final* score,
not an assured match to any specific sportsbook. Actual eventual
betting picks require exact market ID, governing rules, observations,
fees and validation.

## Commands

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_parity_research.py -v
PYTHONPATH=src python src/parity_research.py --history-days 21
PYTHONPATH=src python src/parity_discord.py --report out/statrally-parity-research.json
```

The previous BTTS pipelines remain operational and unchanged on this
milestone. We do not overwrite historical BTTS model or result records
with parity records. A permanent removal of BTTS, Discord command
changes, and mobile UI market selection need separate tested migration.
