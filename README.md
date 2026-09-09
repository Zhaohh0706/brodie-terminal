# $BRODIE V2 Terminal

Single-file dashboard for **$BRODIE V2** on Robinhood Chain (chainId 4663),
modelled on the $PONS Terminal at stateofblocks.com. No build step, no backend.

    open index.html          # or serve it: python3 -m http.server 8731

Drop `index.html` on any static host (Vercel, Netlify, GitHub Pages, S3) as-is.

## How it gets its numbers

The page tries live sources first and falls back to a timestamped snapshot
baked into the `SNAP` object if the browser cannot reach them.

| Panel | Source | Live in the browser? |
|---|---|---|
| Price, liquidity, volume, txns | `api.dexscreener.com` | yes — CORS `*` |
| Supply, dead balances, block | `rpc.mainnet.chain.robinhood.com` `eth_call` | yes — CORS `*` |
| Burn scan | same RPC, `eth_getLogs` over ~25h of blocks | yes |
| Impostor board, comps | DexScreener search | yes |
| Holder count, top holders, buyback audit | offline replay, see below | no — snapshot |

Refresh intervals, RPC list and scan width live in `CONFIG` at the top of the
script. Robinhood Chain runs ~100 ms blocks, so 24h ≈ 864,000 blocks — that is
why the log scan is chunked.

## Re-running the on-chain audit

`tools/onchain_audit.py` replays every V2 `Transfer` event since genesis
(block 49,296,036) and writes `tools/audit.json`: mint distribution, burn
totals, holder count, top holders, and addresses that only ever bought out of
the pool and never sold. Takes a few minutes.

    python3 tools/onchain_audit.py

Then paste the results into the `SNAP` object in `index.html`.

## What the audit found (2026-09-09, block 58,603,719)

- Genesis mint **795,068,399.48** to **562 addresses** — V2 was minted, not
  swapped out of V1. Largest single mint 16.61%, top 10 35.58%.
- **Zero burns.** No transfer to `0x0` or `0x…dEaD` in 32,156 events;
  `totalSupply` has never moved.
- **No buyback address.** 132 wallets only ever bought and never sold, holding
  73.7M (9.3% of supply) — all retail-sized, none treasury-scale.
- V1 `totalSupply` is still exactly 1,000,000,000; only 7.42M V1 (0.74%) has
  reached the v4 PoolManager.

These findings are stated on the page in §04 and §06. If you republish with
different claims, re-run the audit first.

## Splitting into routes

The page is one document with anchor sections (`#contract`, `#supply`,
`#holders`, `#migrate`, `#impostors`, `#peers`, `#origin`, `#sources`,
`#risk`). To match the `/burns`, `/holders`, `/story` sitemap, cut each
`<section>` into its own file and keep the `<style>` block shared.

Not affiliated with Robinhood Markets, Inc.

## Buyback verification (added after the team claimed a 0.6% buyback)

`tools/buyback_audit.py` replays all V2 transfers and ranks every address by
BRODIE bought out of the v4 PoolManager minus BRODIE sold into it, then flags
the addresses that receive a share of the protocol fee stream.

Result at block 58,603,719: the only address provably paid by the fee splitter
bought **581,895.72** BRODIE (**0.073%** of supply) against a claimed 0.6%
(4,770,410 BRODIE) — a 8.2× gap. Several unlinked wallets did buy more than
0.6%, but none has ever received a payout from the splitter.

Two figures that resemble a buyback and are not: the hook took 5,955,651 BRODIE
out of the pool as fee accrual and sold 5,912,531 of it straight back, and the
LP deployer sent 132,045,777.98 into the pool as liquidity. Both are the right
order of magnitude pointing the wrong way.

This is rendered on the page as §04c "Who actually bought".

## Real-time architecture

Modelled on the $PONS Terminal, which is a static page that fetches live APIs in
the browser and reads pre-computed JSON from a CDN
(`data.stateofblocks.com/pons/*.json`). Same split here.

### Live in the browser — no backend needed

| Data | Source | Interval |
|---|---|---|
| Price, liquidity, volume, txns | DexScreener `/tokens/` | 10s |
| Candles (OHLCV) | GeckoTerminal `/networks/robinhood/pools/<poolId>/ohlcv/` | 45s |
| Trade tape | GeckoTerminal `/pools/<poolId>/trades` | 12s |
| m5/m15/m30 stats, reserves | GeckoTerminal `/pools/<poolId>` | 10s |
| Supply, balances, block, any address lookup | Robinhood RPC `eth_call` | 30s |
| Burn scan | Robinhood RPC `eth_getLogs` | 120s |
| Impostor board, comps | DexScreener `/search`, `/tokens/` | 5min |

All four hosts send `Access-Control-Allow-Origin: *`, so this works from any
static host with no proxy. Intervals live in `CONFIG.ms`.

### Baked ledgers — rebuilt by script, pasted into the page

Full-history replays cannot run in a browser (32k+ log events, minutes per pass):

| Ledger | Script | Rows |
|---|---|---|
| Holders, top holders, buyers, burns | `tools/onchain_audit.py` | 779 holders |
| Buyback leaderboard | `tools/buyback_audit.py` | 9 ranked |
| Migration entitlements (`window.ENT`) | `tools/dump_all.py` | 629 depositors |

To make these self-updating, run the scripts on a cron and serve their JSON
next to the page, then `fetch('./data/ledger.json')` instead of using the inline
literal. A GitHub Action on a 15-minute schedule that commits `data/*.json` is
enough — that is exactly the `data.stateofblocks.com` pattern, without paying
for an indexer.

### Interactive pieces

- Tab bar (Tape / Fees & burn / Holders / Migration / Contracts / Chain / About)
- Candle range toggles: 1H / 6H / 24H / 7D / ALL
- Live trade tape with a pause button; new fills flash in
- **Address lookup** — paste any address for live balances, its migration
  deposit and entitlement, whether that entitlement was ever issued, and any
  flagged role (fee beneficiary, hook, launchpad, pool)
- EN / 中文 toggle, light / dark toggle

## Deploying it

One file, no build step, no server, no database. Pick any static host:

**Cloudflare Pages / Netlify** — drag the folder onto the dashboard, or:
```
npx wrangler pages deploy .        # Cloudflare
npx netlify deploy --prod --dir .  # Netlify
```

**Vercel**
```
npx vercel --prod
```

**GitHub Pages** — push the repo, Settings → Pages → deploy from branch. Note the
site URL then contains your GitHub username (`<user>.github.io/<repo>`); attach a
custom domain, or use one of the hosts above, if you would rather not publish
that link between the repo and your account.

The `.github/workflows/refresh-ledgers.yml` job only runs on GitHub. If you host
elsewhere, keep the repo on GitHub for the cron and point the host at it.

### What the page stores and sends

- **Stored on the visitor's device:** one `localStorage` key, `brodie-theme`
  (`"light"` or `"dark"`). Nothing else — no cookies, no sessionStorage, no
  IndexedDB, no analytics, no fingerprinting. Every read and write is wrapped in
  try/catch, so the page works with site data blocked.
- **Sent off the page:** read-only requests to `api.dexscreener.com`,
  `api.geckoterminal.com`, `rpc.mainnet.chain.robinhood.com`,
  `wss://robinhood-rpc.publicnode.com` and Google Fonts. No wallet connection is
  ever requested, no address is ever transmitted anywhere except as a public
  `eth_call` when a visitor types one into the lookup box.
- **Contains no operator identity.** The file has no author name, email, local
  path, repository URL or session identifier in it. Every address it displays was
  discovered on-chain and is public.

Visitors' IP addresses are naturally visible to those five hosts, as with any
page that calls a third-party API. If that matters for your audience, proxy the
calls through your own domain.

## What still needs the team

Everything on this page is either an on-chain fact or an inference from one. The
inferences are marked, and §12 lists the eight questions only the team can close:

1. Confirm the official contract set (hook, splitter, operator, launchpad)
2. Who the four fee beneficiaries are and what each share funds
3. Which address does the buybacks — the 0.6% claim vs the 0.073% measured
4. The 68 unissued entitlements (56,344,918 BRODIE) — deadline, bug, or pending
5. The migration ratio tiers (one deposit credited at exactly 0.6, blended 0.731)
6. Whether the 132,045,778 initial LP is locked, for how long, and by whom
7. Whether a burn mechanism is planned — zero burns to date
8. A published policy for what fee revenue is for

Each answered question converts a panel from "inferred" to "on-chain +
confirmed". That is the only thing this dashboard cannot do for itself.
