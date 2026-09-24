#!/usr/bin/env python3
"""Check that the page can still read its own data, with no browser.

The refresh job once passed every block-number check while boot() was dead:
a ledger changed shape, a renderer threw, and the page sat on a stale snapshot.
This asserts the shape of every file the page fetches, that index.html still
points at them, and that its script parses. Runs in milliseconds.

  python3 scripts/smoke.py
"""
import json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
html = (ROOT / "index.html").read_text()
fails, checked = [], []


def data(name):
    p = ROOT / "data" / name
    if not p.exists():
        fails.append("data/%s is missing" % name)
        return None
    try:
        return json.loads(p.read_text())
    except Exception as e:
        fails.append("data/%s is not valid JSON: %s" % (name, e))
        return None


def require(obj, name, keys):
    if obj is None:
        return
    missing = [k for k in keys if k not in obj]
    if missing:
        fails.append("data/%s is missing %s, which the page reads" % (name, ", ".join(missing)))
    else:
        checked.append(name)


# Keys below are the ones the page dereferences. Add an access in the page, add it here.
hold = data("hold.json")
require(hold, "hold.json", ["block", "generated", "holders", "flows"])
if hold and len(hold.get("holders", {})) < 100:
    fails.append("data/hold.json has only %d holders — the replay probably failed" % len(hold["holders"]))

tl = data("tl.json")
require(tl, "tl.json", ["block", "generated", "parties", "daily", "sweeps", "payouts"])
if tl and tl.get("burns"):
    b = tl["burns"]
    if not isinstance(b.get("burns"), list) or not all(k in b for k in ("count", "totalBurned", "totalEth", "generated")):
        fails.append("data/tl.json burns block is missing count/totalBurned/totalEth/generated/burns")
    elif any(not all(k in x for k in ("seq", "t", "blk", "tx", "eth", "tokens", "spot", "ema", "frac")) for x in b["burns"]):
        fails.append("data/tl.json burns rows are missing fields the page reads")
if tl and tl.get("daily") and tl.get("parties"):
    if any(len(d[1]) != len(tl["parties"]) for d in tl["daily"]):
        fails.append("data/tl.json daily rows do not match its party list")

ent = data("ent.json")
if ent is not None:
    bad = [a for a, v in list(ent.items())[:50] if not (isinstance(v, list) and len(v) == 3)]
    if bad or len(ent) < 100:
        fails.append("data/ent.json rows must be [v1In, v2Entitled, claimed]; bad: %s" % bad[:3])
    else:
        checked.append("ent.json")

for name in ("hold", "tl", "ent"):
    if "loadData('%s')" % name not in html:
        fails.append("index.html no longer fetches data/%s.json" % name)
if re.search(r"window\.(HOLD|ENT|TL|SA|TEAMEXIT)=\{", html):
    fails.append("index.html still carries an inline ledger literal; ledgers live in data/")

# the page must still parse as JavaScript
try:
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
print("smoke test passed — %s" % ", ".join(checked))
