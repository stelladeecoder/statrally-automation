# NFL ATD morning watchlist handoff

The public consumer expects the private `main` branch of
`stelladeecoder/statrally-even-odd-models` to provide:

- Workflow: `.github/workflows/nfl-atd-morning-watchlist-source.yml`
- Artifact: `nfl-atd-morning-watchlist`
- File: `nfl-atd-morning-watchlist.json`

The producer must emit a verified `NFL ATD` / `Kalshi` artifact with
`paper_only: true`, `orders_placed: 0`, Central date and fixtures. Each fixture
must carry verified schedule data; active-player rows must carry an inactive
check and either a verified `KXNFLANYTD-*` contract or an explicit unmatched
state.

The consumer deliberately does not fabricate a slate. If the private workflow
has no successful run, the artifact cannot be downloaded, or the expected file
is absent, the scheduled job exits successfully without a Discord post.
