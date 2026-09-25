# $BRODIE Terminal

Live dashboard for $BRODIE on Robinhood Chain (chain id 4663): the burn vault,
fees, the V1 → V2 claim, market data and holders. Static site, no backend.

Live at https://brodieonhood.com (the old brodie-terminal.vercel.app redirects there)

    python3 -m http.server 8731     # local preview at http://localhost:8731

## Layout

```
index.html          the page: markup, styles and script in one file
data/               ledgers the page fetches (written by scripts/inject.py)
  hold.json           every holder + large pool flows; the page streams new transfers on top
  tl.json             daily fee payouts per recipient; shown until the live scan finishes
  ent.json            V1 deposits per address; fetched only when someone checks an address
assets/             logo, hero video + poster, memes (assets/memes/s = stickers, /g = gallery)
tools/              full-history replays that produce the ledgers (run by the refresh job)
scripts/inject.py   tools/*.json → data/*.json
scripts/smoke.py    checks data/ has the shape the page reads and that the script parses
keeper/keeper.py    calls burnNow() on the vault when its window is open
```

## Where the numbers come from

| What | Source | Refresh |
|---|---|---|
| Price, liquidity, volume | DexScreener | 10 s |
| Candles and trades (Market tab only) | GeckoTerminal | 45 s / 12 s |
| Supply, minted, credits, balances | Robinhood Chain RPC `eth_call` | 30 s |
| Fees | escrow `Credited` events, scanned incrementally | 90 s |
| Burn vault state and burns | vault views + `Burned` events | 60 s |
| Holders | `data/hold.json` + live `Transfer` stream over websocket | live |

Polling pauses while the tab is hidden, only the open tab re-renders, and log
scans only fetch blocks they have not seen yet.

Fees count as BRODIE's when a payout transaction pays one of BRODIE's creator
recipients: the live one (the burn vault since 2026-09-24) or a former one
(`CONFIG.formerCreators`). The hook and escrow are shared by every Pons token.

## Jobs

- `.github/workflows/refresh-ledgers.yml` (every 30 min): replays the chain in
  `tools/`, writes `data/`, runs the smoke test, commits. A push to `main`
  deploys through Vercel's Git integration.
- `.github/workflows/burn-keeper.yml` (every 15 min): runs `keeper/keeper.py`.
  Needs the variable `VAULT_ADDRESS` and the secret `KEEPER_KEY`. The keeper
  wallet has no privileges; when it runs low on gas it waits for the vault's
  0.5% caller tip (paid after 27 idle hours) to refill.

To refresh by hand: `cd tools && sh refresh_all.sh`.

## Adding memes

Drop a square `.webp` into `assets/memes/s` (hero sticker, about 360 px) or
`assets/memes/g` (story gallery, about 720 px) and add its name to `STICKERS`
or `GALLERY` in `index.html`. Three stickers and four gallery images are picked
at random on every visit.

Not affiliated with Robinhood Markets, Inc.
