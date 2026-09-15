#!/usr/bin/env python3
"""Assert every baked data literal still matches the shape the page reads.

On 15 September sell_attrib.json was wired into inject.py and written verbatim.
It carries {categories:{...}, topClaimDumpers:[...]}; renderSellers reads
sa.cats as [[name, value], ...] and sa.topDumpers. sa.cats.find threw,
renderSellers threw, renderAll threw, and boot() never finished — so every
panel, including live price and chain block, silently served a six-day-old
snapshot behind a status chip stuck on BOOT.

The refresh job's existing check compared block numbers inside the file, which
all matched. Nothing checked that the page could still read its own data. This
does, and it runs in milliseconds with no browser.

  python3 scripts/smoke.py
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
html = (ROOT / "index.html").read_text()
fails, checked = [], []

def literal(name):
    m = re.search(r"window\.%s=(\{.*?\});" % name, html, re.S)
    if not m:
        fails.append("window.%s literal is missing from index.html" % name)
        return None
    try:
        return json.loads(m.group(1))
    except Exception as e:
        fails.append("window.%s is not valid JSON: %s" % (name, e))
        return None

def require(obj, name, keys):
    if obj is None:
        return
    missing = [k for k in keys if k not in obj]
    if missing:
        fails.append("window.%s is missing %s — the page reads %s and will throw"
                     % (name, ", ".join(missing), " / ".join(keys)))
    else:
        checked.append(name)

# Keys below are the ones the render functions actually dereference. If you add
# an access in the page, add it here too, or the next shape drift ships silently.
sa = literal("SA")
require(sa, "SA", ["block", "generated", "totalSold", "sellers", "cats", "topDumpers"])
if sa and isinstance(sa.get("cats"), list):
    names = [c[0] for c in sa["cats"] if isinstance(c, list) and c]
    for need in ("fee_hook", "claim_dump"):
        if need not in names:
            fails.append("window.SA.cats has no '%s' row — renderSellers indexes it by "
                         "name and would read undefined" % need)
    if not all(isinstance(c, list) and len(c) == 2 for c in sa["cats"]):
        fails.append("window.SA.cats must be [[name, value], ...]")
if sa and isinstance(sa.get("topDumpers"), list) and sa["topDumpers"]:
    if not all(isinstance(r, list) and len(r) == 3 for r in sa["topDumpers"]):
        fails.append("window.SA.topDumpers must be [[address, sold, minted], ...]")

require(literal("TL"), "TL", ["block", "generated", "parties", "daily", "buys",
                              "firstSweep", "lastSweep", "sweeps", "lastPayout", "payouts"])
require(literal("HOLD"), "HOLD", ["block", "generated", "holders", "flows"])
require(literal("TEAMEXIT"), "TEAMEXIT",
        ["feeWallet", "subWallet", "router", "firstBuy", "lastBuy", "bought", "buyCount",
         "exit", "spentEth", "recvEth", "netEth", "sold", "avgBuyGwei", "avgSellGwei"])

ent = literal("ENT")
if ent is not None:
    bad = [a for a, v in list(ent.items())[:50] if not (isinstance(v, list) and len(v) == 3)]
    if bad:
        fails.append("window.ENT rows must be [v1In, v2Entitled, issued]; bad: %s" % bad[:3])
    else:
        checked.append("ENT")

# the page must still parse as JavaScript
try:
    import subprocess
    r = subprocess.run(["node", "-e",
        "const fs=require('fs');const h=fs.readFileSync(process.argv[1],'utf8');"
        "const m=h.match(/<script>([\\s\\S]*?)<\\/script>\\s*<\\/body>/);new Function(m[1]);",
        str(ROOT / "index.html")], capture_output=True, text=True, timeout=60)
    if r.returncode:
        fails.append("index.html script block is not valid JavaScript: %s" % r.stderr.strip()[:200])
    else:
        checked.append("JS syntax")
except FileNotFoundError:
    pass          # node absent: skip rather than fail the refresh job

if fails:
    print("SMOKE TEST FAILED")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("smoke test passed — %s all match what the page reads" % ", ".join(checked))
