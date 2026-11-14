# Total-score EVEN/ODD market rules and verification gate

Reviewed November 14, 2026. **Published rules are not a verified live bet slip.**
This project contains no market IDs, executable prices, fee schedules or
authorization to claim a wagering edge.

## Verified public rule text

| Provider / source | Market | Supported rule facts | Open issues |
| --- | --- | --- | --- |
| bet365 U.S. soccer [goalscoring markets](https://help.bet365.com/s/en-us/sportsrules/soccer/goalscoring-markets) | Goals Odd/Even | An official 0-0 counts as EVEN; a team scoring zero counts as EVEN in team-specific markets | Exact fixture offering, event market ID, current odds and permitted jurisdiction |
| [Fanatics Missouri house rules](https://sportsbook.fanatics.com/legal/mo/house-rules) | Soccer Odd or Even Goals | Two-way total-goals parity; zero goals classed EVEN | Exact match market availability, normal-time settlement for specific listing, current odds |
| [Fanatics New York house rules](https://sportsbook.fanatics.com/legal/ny/house-rules) | Hockey Total Goals Odd/Even | Full-game markets include overtime goals and one goal added for shootout winning team; 0-0 after regulation counts EVEN in markets excluding OT | Different state edition, exact game/period market and currently offered odds |

The New York and Missouri publications cannot be assumed to govern the
user's sportsbook account or every state. The same sport can have
regulation-only, full-game or period-specific parity markets. Do not map
a full-game NHL ESPN scoreboard probability to a regulation-only contract.

The usual market called `totals` or Over/Under is **NOT** EVEN/ODD.
A listing must explicitly identify an Odd/Even parity proposition.

## Read-only contract verification checklist

Every proposed market needs:

1. A verified sportsbook/provider ID, specific sporting event ID, and
   exact market ID tied to the two verified teams and match start time.
2. A specified outcome basis: soccer 90 minutes plus stoppage, NHL
   60-minute regulation, or NHL final score including OT and shootout.
3. The exact governing jurisdiction/rule version and decisions covering
   abandoned, postponed and 0-0 games.
4. Timestamped pregame prices for EVEN **and** ODD, relevant fees/vig,
   and evidence that the listing could actually be traded.
5. Expected-value calculation on **locked forward predictions**,
   not retroactive best-possible odds.

No rules-only evidence above establishes live sportsbook market
availability or executable odds. **Do not label any forecast a qualified
bet** while these conditions are unverified.

## Product decision

StatRally's November 14, 2026 deployment is a research beta. All
upcoming soccer and NHL matches may be researched independently of
market availability, but they must remain clearly marked as unpriced,
uncalibrated, and not approved betting picks.
