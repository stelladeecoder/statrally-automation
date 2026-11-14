# NHL posts to a different Discord channel

The Even/Odd research beta produces **two independent posts**:
- Soccer -> `STATRALLY_PARITY_SOCCER_WEBHOOK` if present, otherwise the existing `STATRALLY_PARITY_DISCORD_WEBHOOK` / `STATRALLY_DISCORD_WEBHOOK`.
- NHL -> **only** `STATRALLY_PARITY_HOCKEY_WEBHOOK`, with no fallback to the soccer webhook.

## Owner setup

1. In Discord, create or choose the NHL-only channel, e.g. `#nhl-even-odd`.
2. In that channel, go to **Edit Channel -> Integrations -> Webhooks -> New Webhook** (requires Manage Webhooks permission). Choose the NHL channel and copy its private URL.
3. In `stelladeecoder/statrally-automation` go to **Settings -> Secrets and variables -> Actions -> New repository secret** and add `STATRALLY_PARITY_HOCKEY_WEBHOOK` with that URL.
4. Do **not** paste the webhook into chat, code or README. The soccer webhook may remain unchanged. If you want a dedicated soccer channel too, add `STATRALLY_PARITY_SOCCER_WEBHOOK` from that channel.
5. Verify channel routing on the next scheduled workflow run. On an already reserved day, the bot deliberately does not resend a duplicate. A failed/uncertain post must be investigated manually, not blindly retried.

Without the dedicated NHL secret, NHL delivery returns `webhook_missing` and **does not send NHL picks to the soccer channel**. Soccer delivery remains independently attempted. A matching NHL and soccer webhook is rejected.

These remain experimental, read-only research forecasts and not verified wager recommendations.
