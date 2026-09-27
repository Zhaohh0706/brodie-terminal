#!/usr/bin/env python3
"""Write the replayed ledgers to data/*.json, which the page fetches.

  data/hold.json  every holder + large pool flows; the page streams new
                  Transfer events on top, so this only has to be roughly fresh
  data/ent.json   migration deposits per address; fetched only when someone
                  checks an address on the Claim or Holders tab
  data/tl.json    daily fee payouts per recipient, plus the vault's burn list
                  and a market snapshot; shown until the live reads land
  data/audit.json mint totals per recipient and the never-sold count; the page
                  starts its mint scan from here instead of from genesis

Run after the tools/ scripts; scripts/smoke.py checks the result. Keeping the
data out of index.html means a refresh never rewrites the page itself.
"""
import collections, datetime, json, pathlib, sys

root = pathlib.Path(__file__).resolve().parent.parent
out = root / "data"
out.mkdir(exist_ok=True)


def rnd(x):
    x = float(x)
    r = round(x, 6)
    return 1e-9 if x <= 0 or r == 0 else r      # sub-micro dust: floored, still a holder


def load(name):
    return json.loads((root / "tools" / name).read_text())


def write(name, obj):
    (out / name).write_text(json.dumps(obj, separators=(",", ":")))


# ── holders + pool flows ────────────────────────────────────────────────
h = load("holders_all.json")
write("hold.json", {
    "block": h["block"], "generated": h["generated"],
    # exact wei as decimal strings when the replay has them; the page streams BigInt deltas on top
    "holders": h["wei"] if "wei" in h else {a: rnd(v) for a, v in h["holders"].items()},
    "flows": {a: [rnd(v[0]), rnd(v[1])] for a, v in h["flows"].items() if max(v[0], v[1]) >= 250000},
})

# ── migration entitlements ──────────────────────────────────────────────
e = load("entitlements_all.json")["all"]
write("ent.json", {a: [rnd(v[0]), rnd(v[1]), v[2]] for a, v in e.items()})

# ── fee timeline, aggregated per day per beneficiary ────────────────────
tl = load("timeline.json")
# BRODIE pays exactly two recipients, 70/30, and the ledger names them itself
# so this stays right when the creator side moves. Older ledgers carried four
# parties because the shared escrow was read without a per-token filter.
if "creator" not in tl:
    sys.exit("timeline.json predates the 70/30 fix — rerun tools/timeline.py")
# Every address that ever held the creator role keeps its own column; the live
# one comes first. Since 2026-09-24 that is the burn vault, then the old wallet.
VAULT = "0xc0f342a8936755697c535f1e8e0d712a8da672f8"
creators = tl.get("creators") or [tl["creator"]]
PARTIES = [(a, "burn vault" if a == VAULT else "creator" if i == 0 else "creator → 24 Sep", 70.0)
           for i, a in enumerate(creators)] + [(tl["protocol"], "protocol", 30.0)]
idx = {a: i for i, (a, _, _) in enumerate(PARTIES)}
daily = collections.defaultdict(lambda: {"eth": [0.0] * len(PARTIES), "sw": 0, "sold": 0.0})
for ev in tl["events"]:
    day = datetime.datetime.fromtimestamp(ev["t"], datetime.timezone.utc).strftime("%Y-%m-%d")
    if ev["kind"] == "payout" and ev.get("to") in idx:
        daily[day]["eth"][idx[ev["to"]]] += ev["eth"]
    elif ev["kind"] == "sweep":
        daily[day]["sw"] += 1
        daily[day]["sold"] += ev["tokens"]
sweeps = [ev for ev in tl["events"] if ev["kind"] == "sweep"]
payouts = [ev for ev in tl["events"] if ev["kind"] == "payout" and ev.get("to") in idx]
buys = [ev for ev in tl["events"] if ev["kind"] == "buy"]
write("tl.json", ({
        "generated": tl["generated"], "block": tl["block"],
        "parties": [[a, l, sh] for a, l, sh in PARTIES],
        "daily": [[d, [round(x, 4) for x in daily[d]["eth"]], daily[d]["sw"], round(daily[d]["sold"])]
                  for d in sorted(daily)],
        "buys": [{"t": b["t"], "blk": b["blk"], "who": b["to"],
                  "tokens": round(b["tokens"], 2), "tx": b["tx"]} for b in buys],
        "firstSweep": sweeps[0]["t"], "lastSweep": sweeps[-1]["t"], "sweeps": len(sweeps),
        "firstPayout": payouts[0]["t"], "lastPayout": payouts[-1]["t"], "payouts": len(payouts),
        # exact ETH per recipient through "block": the page's live fee scan starts from here
        "credited": {a: round(sum(ev["eth"] for ev in payouts if ev["to"] == a), 12) for a, _, _ in PARTIES},
        # every burn so far (tools/burns.py): the page paints its burn panel from this before
        # its own chain read lands, and keeps it, marked as a snapshot, if the RPC is down
        "burns": load("burns.json") if (root / "tools" / "burns.json").exists() else None,
        # last DexScreener read by the ledger job (tools/market.py): the page's offline fallback
        "market": load("market.json") if (root / "tools" / "market.json").exists() else None,
        # total supply from the full Transfer replay, the fallback while the chain can't be read
        "supply": (lambda a: {"block": a["block"], "total": round(a["supply_from_logs"], 6)} if "supply_from_logs" in a else None)(load("audit.json")),
    }))

# ── mint totals + never-sold, from the full Transfer replay (tools/onchain_audit.py) ──
# The page used to rebuild these from genesis on every visit: ~25M blocks of logs, the
# slowest thing it did and the first to hit the RPC's rate limit when many people load
# at once. Now it starts from this file and scans only the blocks after "block".
a = load("audit.json")
if "mint_count" in a:
    MIGRATOR = "0x9310bc8bf95fa35608a9f08f76b55b4fdddc1ef0"
    rec = {addr.lower(): v for addr, v in a["mint_recipients"]}
    write("audit.json", {
        "block": a["block"], "generated": a["generated"],
        "mints": {"count": a["mint_count"], "seed": round(rec.get(MIGRATOR, 0), 6),
                  "first": a["mint_first"], "last": a["mint_last"],
                  "byAddr": {k: round(v, 4) for k, v in rec.items() if k != MIGRATOR}},
        "neverSold": {"count": a["never_sold_count"], "total": round(a["never_sold_total"], 2)},
    })

print("wrote data/: %d holders, %d entitlements, %d fee days, holders at block %d"
      % (len(h["holders"]), len(e), len(daily), h["block"]))
