# StatRally multi-sport EVEN/ODD expansion proposal

**Status: planning / research only.** The existing soccer BTTS model,
Discord delivery, public app, and automated workflows remain unchanged.
No new parity market has been validated or launched.

## Supported sports scope for the proposed parity platform

| Family | Competition | Scope | Rollout |
| --- | --- | --- | --- |
| Soccer | Men's club and international soccer | Total regulation goals EVEN/ODD | Phase 1 pilot |
| Soccer | Women's club and international soccer | Separate leagues and national-team competitions, including women's World Cup and major domestic leagues | Phase 1+ after source verification |
| Hockey | NHL | Total goals EVEN/ODD, explicit regulation / OT / shootout rules | Phase 2 candidate |
| Baseball | MLB | Total runs EVEN/ODD, explicit extra-innings settlement | Phase 3 candidate |
| Basketball | NBA | Total points EVEN/ODD | Phase 4 candidate |
| Basketball | WNBA | Women's professional basketball, distinct model and league ID | Phase 4 candidate |
| Basketball | NCAA Division I men's basketball | Total points EVEN/ODD, regular season and tournament separately validated | Phase 5 candidate |
| Basketball | NCAA Division I women's basketball | Total points EVEN/ODD, regular season and tournament separately validated | Phase 5 candidate |
| Football | NFL | Total points EVEN/ODD | Phase 6 candidate |
| Football | NCAA college football (FBS first) | Total points EVEN/ODD, bowl/playoff and regulation/OT settlement | Phase 7 candidate |

Other women's soccer and hockey competitions may be added as their
respective data sources, competition identities, betting-market availability
and model validation permit. Do not equate a sport's inclusion in this
roadmap with currently verified sportsbook offerings.

## Design contract

- **Every competition is independently registered** with a durable
  competition ID, sport, gender/category when applicable, season, timezone,
  source, total metric (points/goals/runs), settlement period and provider
  market identity. Women's competitions must not be inherited implicitly
  from men's schemas or pooled into men's training samples.
- The generic parity outcome is `EVEN` for an integer combined total
  divisible by 2; otherwise `ODD`. Validate final status, source identity
  and a clearly chosen regulation/OT/extras settlement basis before grading.
- Preserve **separate probabilities and performance** for EACH sport and
  competition, including women's basketball, women's soccer and NCAA women's
  basketball. Never imply that sharing an engine validates shared models.
- Run chronological train/validation/test splits with no same-day/future
  leakage and compare to 50/50, historical parity prevalence and
  sportsbook implied probabilities including fees/vig.
- Do not automatically promote a predictive model or publish
  `qualified_bet=true` unless independent holdout, calibration,
  price/fee rules and exact market mapping pass predefined gates.
- Every league can be enabled independently for fixture collection,
  research forecasts, verified outcomes, Discord posts and dashboard
  release. **One sport or league launches at a time**.
- Women's league coverage is a formal acceptance criterion, not a
  discretionary later enhancement; show `unsupported`,
  `data_unverified` or `market_unavailable` rather than silently omit.
- Existing BTTS products remain active until the owner separately approves
  replacing them. Archive their historical research and delivery receipts
  rather than overwriting them as parity records.

## First milestones

1. Confirm soccer parity market provider, settlement scope, and historical
   data permissions for men's AND women's competitions.
2. Create a shared parity grader with sport/competition adapters and
   explicit final-score/period verification; develop tests for
   all listed categories, especially women's fixtures.
3. Run an offline chronological soccer Poisson parity backtest and a
   simple prevalence baseline, segmented by competition and gender.
4. Release research-only soccer parity beta when the grading/data
   path is audited. Do not assert a profitable edge without price history.
5. Extend to NHL, MLB, NBA/WNBA, NCAA men's/women's basketball,
   NFL and NCAA football one validated competition at a time.

## Decisions intentionally open

- Whether to retire BTTS or maintain two research products within StatRally.
- Which sportsbooks supply an actual parity market for each league.
- Exact league launch sequence and licensed historical data providers.
- Whether college football expands beyond FBS, and whether additional
  women's college/professional sports become available with verified feeds.
