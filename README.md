<div align="center">

# ⚽ StatRally
#
### Milestone 3: Private model research connection

StatRally's private `statrally-even-odd-models` repository exports timestamped soccer parity **research forecasts** with source-run and historical-validation provenance. The public [model evidence workflow](.github/workflows/parity-model-evidence-sync.yml) authenticates read-only to its private Actions artifact, validates SHA/run identity, 13-league research coverage, prematch timing and zero-bet gates, and records a sanitized **research-only** GitHub Issue. [Owner token setup and verification](docs/parity_model_handoff.md) are mandatory before claiming the cross-repository sync is live. No private datasets are copied, no model is automatically promoted, and no Discord watchlist, picks, results or legacy BTTS workflow is changed by this connection.

## The Edge Is in the Data.

**Soccer + NHL Even/Odd research. Verified game scores.**

![Status: Coming Soon](https://img.shields.io/badge/Mobile%20App-Coming%20Soon-0891b2?style=for-the-badge)
![Free](https://img.shields.io/badge/Access-Free-16a34a?style=for-the-badge)

## 📱 Mobile Experience Coming Soon

**A mobile-friendly StatRally experience is on the way.**

Preview access will be announced here when the app is ready.

</div>

---

## ⚽ What is StatRally?

StatRally is an independent sports analytics project. **Soccer and NHL Even/Odd (total-score parity) research beta launched November 14, 2026**, with a successful source-verified workflow and a confirmed Discord research-status message. Predictions are experimental and **not betting recommendations**. The older soccer BTTS research pipeline is retained separately during the transition.

## ✨ What to expect

- Daily **soccer and NHL EVEN/ODD research** reports using publicly accessible scoreboards, with separate competition histories.
- Soccer fixture discovery now covers **13 men's competitions** (Premier League, Bundesliga, LaLiga, Serie A, Ligue 1, Eredivisie, Liga Portugal, Brasileirão Série A, MLS, Liga MX, Argentine Primera División, UEFA Champions League, UEFA Europa League) and **two women's competitions** (NWSL, UEFA Women's Champions League). Coverage means configured source scans, not a guarantee of fixtures each day.
- Experimental EVEN/ODD probabilities using a historical league baseline. Not validated as a betting edge.
- Independently verified match outcomes.
- Daily, weekly and monthly accuracy recaps.
- Model-performance insights.

The mobile experience is **not yet publicly available**. There is no registration or invitation link at this time.

## 🏟️ EVEN/ODD research beta

On November 14, 2026, the multi-sport research pipeline completed a successful production scan with **358 historical final-score records, 15 upcoming fixtures and 15 experimental parity forecasts** across eight configured competitions. Discord acknowledged the research-status message. This is a **research beta**, not an odds-integrated, calibrated, or wager-qualified picks service.

**Coverage validation (November 14):** the 16-competition soccer/NHL research scan passed on the expansion branch, finding **18 upcoming fixtures**, with **568 historical final scores** available inside the 21-day research scan. These totals cover all sports combined. An independently graded, matchup-specific parity model has **not** been promoted. The originally frozen November 14 Discord snapshot had fewer configured leagues and remains historical evidence; we do not retroactively alter its issued predictions.

**Clear repository ownership:** The private [`statrally-even-odd-models`](https://github.com/stelladeecoder/statrally-even-odd-models) repository owns the NEW experimental soccer parity model work, historical 13-league scoring data and validation. It also retains legacy BTTS model artifacts unchanged. The public `statrally-automation` repository controls scheduling, fixture scans, Discord watchlists, immutable historical receipts/results, and the unreleased dashboard. A temporary parity baseline still exists here solely for research; **the private model has not been connected to the public prediction workflow**. No betting picks or market prices are published by the baseline. NHL watchlists are schedule-only.

View [launch scope and verification limits](docs/parity_soccer_nhl_beta_launch.md) and [verified market-rule research](docs/parity_market_rules.md). NHL full-game scoreboard parity and 60-minute regulation parity are different contracts; we do not assume sportsbook market equivalence.

**Forward performance milestone:** Each new research slate is archived before its Discord status post. A separate daily workflow checks original saved probabilities against independently verified game finals and records immutable EVEN/ODD outcomes, preserving missing or pending results. The optional read-only GitHub Pages build includes a separate mobile-friendly **Even/Odd dashboard**; public hosting and future scheduled delivery must be verified independently. No historical BTTS result is overwritten.

Additional sports (NBA, WNBA, college men’s and women’s basketball, NFL, NCAA football and MLB) remain roadmap items, not live integrations.

## 📊 Research transparency

StatRally predictions are experimental. Historical accuracy does not guarantee future outcomes; no proven betting edge or verified parity odds are claimed. Fixture discovery, market availability, model eligibility and successful Discord delivery are separate checks; incomplete feeds must not be presented as confirmed zero-game days. StatRally does not place trades or wagers. Existing BTTS automation remains separate until explicitly migrated.

---

<sub>© 2026 StatRally. Independent multi-sport analytics project.</sub>
