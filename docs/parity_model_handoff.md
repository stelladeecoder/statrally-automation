# Milestone 3: Private model research handoff

The private `stelladeecoder/statrally-even-odd-models` project owns
training data, model candidate code, historical holdout evaluation and
research probability generation. Public `statrally-automation` owns
scheduling, delivery, source verification, immutable public audit and
Discord/web views.

**Important:** This bridge connects private model output to a public
**research evidence ledger**, not to live picks. No candidate is promoted
or posted in watchlists, picks or results channels. The existing
soccer/NHL public parity baseline and the older BTTS workflows are
unchanged. The candidate is **not calibrated or proven to outperform a
50/50 baseline**. A model must pass independently specified chronological,
calibration and verified-market gates before any public picks workflow
can use it.

## Timing and artifact

1. Public competition scan runs at `09:15 UTC` daily, preserving the
   original pregame slate in an immutable GitHub Issue.
2. Private `parity-model-handoff.yml` runs at `10:15 UTC`. It reads the
   original public prematch fixture issue (read only), scores only
   source-verified and exact historical team-name matches before kickoff,
   and exports `model-handoff.json` in a *private* GitHub Actions artifact.
   Missing historical team identities are reported as
   `team_identity_unconfirmed` rather than guessed. Models from the 13
   legacy men's soccer leagues have a future holdout and a research-only
   status. Women's soccer data/models remain out of this bridge pending
   source verification.
3. Public `parity-model-evidence-sync.yml` runs at `11:15 UTC` and
   validates the artifact's run ID, 40-character commit SHA, workflow
   status, freshness, exact 13-league evaluation and zero-bet policy.
   It copies only a small, sanitized evidence projection into a
   bot-authored GitHub Issue. It **never sends forecasts to Discord**.

## Required one-time owner setup

Create a fine-grained GitHub personal access token with access **only**
to the private `statrally-even-odd-models` repository, with repository
permission **Actions: Read-only** (plus Metadata: Read).

In public `statrally-automation` repository:
**Settings → Secrets and variables → Actions → New repository secret**

- Secret name: `STATRALLY_MODELS_READ_TOKEN`
- Secret value: the token. Never paste the token in chat, source code,
  README, logs, artifacts or Discord.

Without that secret, the public read workflow **cannot authenticate** to
the private run artifact and the model sync will fail. It does not
fall back to stale or unverified probabilities. Configure and check the
workflow in GitHub Actions before claiming live inter-repository sync.

## Current boundaries

This is an initial research connection only. Before considering model
promotion, add matchup identity mappings vetted against ESPN, meaningful
out-of-sample accuracy/calibration metrics versus fair baselines,
provider-specific odds and fee verification, model version integrity,
secure audited deployment controls and an explicit, independent approval.
The Poisson parity research candidate mathematically favors EVEN by
construction and does not establish an exploitable sportsbook edge.

The existing 13 men's + 2 women's league fixture discovery and NHL
schedule-only Discord channels stay unchanged. Milestone 4 NHL
results-channel publishing is deferred.
