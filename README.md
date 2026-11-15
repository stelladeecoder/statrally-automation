<div align="center">

# 🏒 StatRally

### The Edge Is in the Data.

**NHL Moneyline Analytics · Kalshi Paper Trading**

![Access: Free](https://img.shields.io/badge/Access-Free-16a34a?style=for-the-badge)
![Mobile App: Coming Soon](https://img.shields.io/badge/Mobile%20App-Coming%20Soon-0891b2?style=for-the-badge)
![NHL Moneyline: Research](https://img.shields.io/badge/NHL%20Moneyline-Research%20Beta-64748b?style=for-the-badge)
![Execution: Paper Only](https://img.shields.io/badge/Trading-Paper%20Only-0891b2?style=for-the-badge)

A mobile-friendly way to follow **NHL game-winner probabilities**, compare them with available Kalshi market prices, and track transparent hypothetical paper results.

**Free access. Mobile experience coming soon.**

</div>

---

## What is StatRally?

StatRally is an independent sports analytics research project focused on **full-game NHL Moneyline** outcomes: **which team will win?**

The model estimates each team's pregame win probability. A separate market-data process matches the matchup to the correct **Kalshi NHL winner contract** and checks its observed price, applicable fees and available orderbook depth. A forecast is not automatically a pick or a profitable trade.

**StatRally currently conducts paper-only research. It does not place real-money trades or wagers.** All displayed theoretical results must be understood as hypothetical.

## NHL Moneyline experience

| Discord channel | Purpose | Format |
|---|---|---|
| **`#nhl-watchlist`** | Full NHL slate with verified matchups, model win probabilities, Kalshi executable ask, fee, depth, Net EV when supported, tier, and **NO BET** games | Clean **blue** daily card |
| **`#nhl-picks`** | Only independently verified, qualified **[PAPER TRADE]** signals when all post-fee model and market gates are satisfied | **Teal** qualified-picks card |
| **`#nhl-results`** | Independently verified settlements, entry versus pre-puck closing ask, quote-based CLV proxy, post-fee hypothetical P&L and cumulative paper scorecard | **Green WIN**, **red LOSS**, plus running-summary card |
| **`#admin`** | Private operational health: scheduler activity, delivery receipts, entry/close snapshot hits and misses, Kalshi API issues and low-liquidity skips | Daily health report |

The Discord webhook connections have been verified. **The new Moneyline reports are not yet on an automated daily publishing schedule**: the first genuine entry-to-closing-to-settlement paper cycle must pass validation before that schedule is activated.

### What the numbers mean

- **Model Win Prob:** The model's estimated probability that the selected team wins the defined full-game matchup.
- **Kalshi Executable Ask:** The price inferred from the current opposing orderbook bids at the hypothetical contract size. A displayed quote is **not** an actual execution.
- **Fee and Orderbook Depth:** The estimated or verified applicable transaction cost and the available quantity supporting that quote.
- **Net EV:** Hypothetical expected value after applicable fees, shown only when the required market and fee inputs are verified. Otherwise the game stays **NO BET**.
- **Odds Tier:** **Underdog** (selected YES ask below $0.50), **Short Favorite** ($0.50–$0.59), or **Heavy Favorite** ($0.60+).
- **CLV:** The movement from the recorded pregame entry ask to the observed near-puck-drop closing ask; a **quote-to-quote proxy**, not a realized fill.

For research, qualifying paper signals are assessed against **+2.5%, +3.5%, and +5.0% post-fee Net EV** thresholds. These are experimental decision rules, **not** a claim that the strategy is profitable.

## Current launch status

- **Verified:** Current-season NHL pregame model inference, team-to-Kalshi contract matching, real read-only orderbook diagnostics, and all three dedicated NHL Discord webhook destinations.
- **Implemented:** A private five-minute prospective snapshot poller and health-receipt workflow. GitHub Actions timing is best-effort, and missed snapshot windows are not backfilled.
- **In validation:** A complete real-game sequence with a 45–60-minute pregame quote, a closing quote 0–5 minutes before puck drop, independently confirmed settlement, and post-fee paper P&L.
- **Not enabled:** Automated daily Moneyline paper-signal publishing or any live order execution.

The research aims to collect and review **150–250 completed, independently logged paper games** before evaluating the evidence. That sample target does **not** automatically authorize real trading.

## Other sports and historical research

StatRally also contains historical soccer fixture-discovery and model-research work. Earlier **NHL Even/Odd** score-parity publishing has been **retired from the NHL Discord channels** in favor of Moneyline research. Historical Even/Odd, Over/Under and soccer research may remain in the repositories for reproducibility but should not be confused with current NHL Moneyline performance.

Configured sports or competitions do not guarantee a game, a qualified prediction, or an available market on every date.

## 📱 Mobile experience coming soon

A mobile-friendly dashboard is under development. Public availability will be announced after verification. There is no active public registration or invitation link listed here.

## Transparency

StatRally provides independent research and hypothetical paper-trading analytics, **not financial advice or guarantees**. Probabilities can be inaccurate; market prices change, liquidity may be insufficient, and fees reduce potential returns. Historical backtests and paper results do not establish future profitability.

**No real-money orders are enabled.**

---

<sub>© 2026 StatRally. The Edge Is in the Data.</sub>
