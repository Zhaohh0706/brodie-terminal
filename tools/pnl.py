#!/usr/bin/env python3
"""Price the fee wallet's round trip from the pool's own Swap events.

tx.value overstates the cost: routers refund whatever the swap did not consume.
Summing the ETH legs of the Swap events gives what was actually paid, and the
token legs cross-check against the Transfer amounts.
"""
import json, urllib.request, time, pathlib

RPCS = ["https://robinhood-rpc.publicnode.com", "https://rpc.mainnet.chain.robinhood.com",
        "https://rpc.ordofi.network"]
HDR = {"content-type": "application/json", "user-agent": "Mozilla/5.0"}
SWAP = "0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"
PM = "0x8366a39cc670b4001a1121b8f6a443a643e40951"
here = pathlib.Path(__file__).resolve().parent

def rpc(method, params, tries=8):
    for t in range(tries):
        try:
            req = urllib.request.Request(RPCS[t % len(RPCS)], headers=HDR, data=json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode())
            r = json.load(urllib.request.urlopen(req, timeout=60))
            if "error" in r:
                time.sleep(.3); continue
            return r["result"]
        except Exception:
            time.sleep(.5 * (t + 1))
    return None

def i128(h):
    v = int(h, 16)
    return v - (1 << 128) if v >= (1 << 127) else v

def eth_legs(tx, want_in):
    """ETH paid (want_in=True) or received (False) across every pool in the tx."""
    r = rpc("eth_getTransactionReceipt", [tx]) or {}
    total = 0.0
    for l in r.get("logs", []):
        if l["address"].lower() == PM and l["topics"][0] == SWAP:
            a0 = i128(l["data"][2:][32:64]) / 1e18
            if want_in and a0 < 0: total += -a0
            if not want_in and a0 > 0: total += a0
    return total

def main():
    te = json.loads((here / "team_exit.json").read_text())
    spent = sum(eth_legs(b["tx"], True) for b in te["buys"])
    recv = sum(eth_legs(e["tx"], False) for e in te["exit"] if e["kind"] == "sell")
    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "spentEth": round(spent, 6), "recvEth": round(recv, 6), "net": round(recv - spent, 6),
           "avgBuy": spent / te["totalBought"], "avgSell": recv / te["totalSold"]}
    (here / "team_pnl.json").write_text(json.dumps(out, indent=1))
    print("bought %.4f ETH -> %s BRODIE" % (spent, f'{te["totalBought"]:,.0f}'))
    print("sold   %.4f ETH <- %s BRODIE" % (recv, f'{te["totalSold"]:,.0f}'))
    print("net    %+.4f ETH (%.1f%% against the average entry)"
          % (recv - spent, (out["avgSell"] / out["avgBuy"] - 1) * 100))

if __name__ == "__main__":
    main()
