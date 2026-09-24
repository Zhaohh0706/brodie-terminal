#!/usr/bin/env python3
"""Re-inject the replayed ledgers into index.html.

Every literal the page reads from disk is rewritten here, so a refresh run
cannot leave one panel current and another frozen — which is exactly how the
9 September sale stayed invisible for two days.

Reads tools/{holders_all,entitlements_all,timeline,flows}.json and rewrites
window.HOLD / window.ENT / window.TL / the live fields of window.TEAMEXIT.
Run after the tools/ scripts. Exits non-zero if any anchor is missing.
"""
import collections, datetime, json, pathlib, re, sys

root = pathlib.Path(__file__).resolve().parent.parent
html_path = root / "index.html"
s = html_path.read_text()


def num(x):
    x = float(x)
    if x <= 0:
        return "1e-9"                      # sub-micro dust: floored, still a holder
    r = round(x, 6)
    if r == 0:
        return "1e-9"
    return str(int(r)) if r == int(r) else ("%.6f" % r).rstrip("0").rstrip(".")


def load(name):
    return json.loads((root / "tools" / name).read_text())


def sub(pattern, replacement, label):
    global s
    s, n = re.subn(pattern, lambda _: replacement, s, count=1, flags=re.S)
    if n != 1:
        sys.exit("anchor not found: %s" % label)


# ── holders + pool flows ────────────────────────────────────────────────
h = load("holders_all.json")
flows = {a: v for a, v in h["flows"].items() if max(v[0], v[1]) >= 250000}
sub(r"window\.HOLD=\{.*?\};",
    'window.HOLD={"block":%d,"generated":"%s","holders":{%s},"flows":{%s}};' % (
        h["block"], h["generated"],
        ",".join('"%s":%s' % (a, num(v)) for a, v in h["holders"].items()),
        ",".join('"%s":[%s,%s]' % (a, num(v[0]), num(v[1])) for a, v in flows.items())),
    "window.HOLD")

# ── migration entitlements ──────────────────────────────────────────────
e = load("entitlements_all.json")["all"]
sub(r"window\.ENT=\{.*?\};",
    "window.ENT={%s};" % ",".join(
        '"%s":[%s,%s,%d]' % (a, num(v[0]), num(v[1]), v[2]) for a, v in e.items()),
    "window.ENT")

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
    day = datetime.datetime.utcfromtimestamp(ev["t"]).strftime("%Y-%m-%d")
    if ev["kind"] == "payout" and ev.get("to") in idx:
        daily[day]["eth"][idx[ev["to"]]] += ev["eth"]
    elif ev["kind"] == "sweep":
        daily[day]["sw"] += 1
        daily[day]["sold"] += ev["tokens"]
sweeps = [ev for ev in tl["events"] if ev["kind"] == "sweep"]
payouts = [ev for ev in tl["events"] if ev["kind"] == "payout" and ev.get("to") in idx]
buys = [ev for ev in tl["events"] if ev["kind"] == "buy"]
sub(r"window\.TL=\{.*?\};",
    "window.TL=" + json.dumps({
        "generated": tl["generated"], "block": tl["block"],
        "parties": [[a, l, sh] for a, l, sh in PARTIES],
        "daily": [[d, [round(x, 4) for x in daily[d]["eth"]], daily[d]["sw"], round(daily[d]["sold"])]
                  for d in sorted(daily)],
        "buys": [{"t": b["t"], "blk": b["blk"], "who": b["to"],
                  "tokens": round(b["tokens"], 2), "tx": b["tx"]} for b in buys],
        "firstSweep": sweeps[0]["t"], "lastSweep": sweeps[-1]["t"], "sweeps": len(sweeps),
        "firstPayout": payouts[0]["t"], "lastPayout": payouts[-1]["t"], "payouts": len(payouts),
    }, separators=(",", ":")) + ";",
    "window.TL")

# ── the live counters inside the team-exit literal ──────────────────────
f = load("flows.json")
m = re.search(r"window\.TEAMEXIT=(\{.*?\});", s, re.S)
if not m:
    sys.exit("anchor not found: window.TEAMEXIT")
te = json.loads(m.group(1))
te.update({"hookFee": f["hookFeeAccrued"], "hookSold": f["hookSold"],
           "chainBought": f["totalBought"], "chainSold": f["totalSold"],
           "txs": f["txs"], "block": f["block"], "generated": f["generated"]})
sub(r"window\.TEAMEXIT=\{.*?\};",
    "window.TEAMEXIT=" + json.dumps(te, separators=(",", ":")) + ";", "window.TEAMEXIT")

# ── sell-side attribution ───────────────────────────────────────────────
# This literal went unrefreshed from launch until 15 September because it was
# never wired into the refresh job — the same failure the correction box in §07
# describes. It is in the pipeline now.
raw = load("sell_attrib.json")
# sell_attrib.py writes {categories: {...}, topClaimDumpers: [...]}; the page reads
# sa.cats as [[name, value], ...] and sa.topDumpers as [[addr, sold, minted], ...].
# Emitting the raw shape is what broke boot() on 15 September — renderSellers threw
# on sa.cats.find and took every other panel down with it. Map it explicitly.
sa = {
    "generated": raw["generated"], "block": raw["block"],
    "totalSold": raw["totalSold"], "sellers": raw["sellers"],
    "cats": sorted(([k, v] for k, v in raw["categories"].items() if v > 0),
                   key=lambda kv: -kv[1]),
    "topDumpers": raw["topClaimDumpers"],
}
for need in ("fee_hook", "claim_dump"):
    if not any(c[0] == need for c in sa["cats"]):
        sa["cats"].append([need, 0])          # renderSellers indexes these two by name
sub(r"window\.SA=\{.*?\};",
    "window.SA=" + json.dumps(sa, separators=(",", ":")) + ";", "window.SA")

html_path.write_text(s)
print("injected %d holders, %d flows, %d entitlements, %d timeline days, sell-attrib block %d, at block %d"
      % (len(h["holders"]), len(flows), len(e), len(daily), sa["block"], h["block"]))
