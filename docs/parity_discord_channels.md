# StatRally NHL Discord channel routing

The owner's existing NHL channels are **#nhl-watchlist**, **#nhl-picks**,
and **#nhl-results**. Do not create a fourth hockey channel.

| Channel | Intended content | Current live state |
| --- | --- | --- |
| `#nhl-watchlist` | Every verified upcoming NHL fixture and research-only EVEN/ODD probabilities, including insufficient-history notices | Implemented; requires owner-supplied webhook |
| `#nhl-picks` | Selected EVEN/ODD predictions only after an independently validated, calibrated sport-specific model and verified exact sportsbook market/odds | **Disabled**; do not post baseline probabilities as approved picks |
| `#nhl-results` | Grades for previously recorded NHL forecasts, posted only after verified final scores and separated from sportsbook settlement | Forward results stored and graded in GitHub; **Discord channel posting not yet implemented** |

## Channel configuration

In Discord, open **Edit Channel → Integrations → Webhooks → New Webhook**
for the existing `#nhl-watchlist` channel. Copy its URL privately.

Add it to GitHub repository
`stelladeecoder/statrally-automation`:
**Settings → Secrets and variables → Actions → New repository secret**.

- Name: `STATRALLY_NHL_WATCHLIST_WEBHOOK`
- Value: The private webhook URL for `#nhl-watchlist`

The existing soccer Discord destination remains unchanged.

The generic `STATRALLY_PARITY_HOCKEY_WEBHOOK` secret is deliberately
**not used** for NHL watchlist posts. No fallback to `#match-watchlist`,
`#nhl-picks`, or `#nhl-results` occurs when the specific watchlist secret
is missing. Do not paste webhook secrets in repository files or chat.

Possible future secrets (not yet consumed by production workflows):
`STATRALLY_NHL_PICKS_WEBHOOK` and `STATRALLY_NHL_RESULTS_WEBHOOK`.
Do not activate either prematurely. The order of work is verified NHL
grading and safe results reporting first, then a separately evaluated
picks publishing policy.

The next verified scheduled run must confirm the intended Discord
channel. Existing same-day posts are reserved and not blindly
resent to prevent duplicates.
