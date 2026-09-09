#!/usr/bin/env python3
"""Re-inject the replayed ledgers into index.html.

Reads tools/holders_all.json and tools/entitlements_all.json and rewrites the
window.HOLD / window.ENT literals in place. Run after the tools/ scripts.
"""
import json, re, pathlib

root = pathlib.Path(__file__).resolve().parent.parent
html = root / "index.html"
s = html.read_text()


def num(x):
    x = float(x)
    if x <= 0:
        return "1e-9"                      # sub-micro dust: floored, still a holder
    r = round(x, 6)
    if r == 0:
        return "1e-9"
    return str(int(r)) if r == int(r) else ("%.6f" % r).rstrip("0").rstrip(".")


h = json.loads((root / "tools/holders_all.json").read_text())
flows = {a: v for a, v in h["flows"].items() if max(v[0], v[1]) >= 250000}
hold = 'window.HOLD={"block":%d,"generated":"%s","holders":{%s},"flows":{%s}};' % (
    h["block"], h["generated"],
    ",".join('"%s":%s' % (a, num(v)) for a, v in h["holders"].items()),
    ",".join('"%s":[%s,%s]' % (a, num(v[0]), num(v[1])) for a, v in flows.items()))

e = json.loads((root / "tools/entitlements_all.json").read_text())["all"]
ent = "window.ENT={" + ",".join(
    '"%s":[%s,%s,%d]' % (a, num(v[0]), num(v[1]), v[2]) for a, v in e.items()) + "};"

s, n1 = re.subn(r"window\.HOLD=\{.*?\};", hold, s, count=1, flags=re.S)
s, n2 = re.subn(r"window\.ENT=\{.*?\};", ent, s, count=1, flags=re.S)
assert n1 == 1 and n2 == 1, "injection anchors not found"
html.write_text(s)
print("injected %d holders, %d flows, %d entitlements at block %d"
      % (len(h["holders"]), len(flows), len(e), h["block"]))
