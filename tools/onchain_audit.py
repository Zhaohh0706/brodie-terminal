#!/usr/bin/env python3
"""Replay every $BRODIE V2 Transfer event and answer three questions:
   how much was burned, how much was bought back, and who holds what.
   Writes audit.json next to this file. Run: python3 onchain_audit.py"""
import json, time, urllib.request, collections, os

RPCS = ["https://rpc.mainnet.chain.robinhood.com", "https://robinhood-rpc.publicnode.com",
        "https://rpc.arrowrpc.com", "https://rpc.ordofi.network"]
HDR = {"content-type": "application/json", "user-agent": "Mozilla/5.0", "accept": "*/*"}
V2 = "0x737054bd706cba68eaF4661411FeDE5F6C2952e5"
V1 = "0x45F82AC5d507e988f7406935da8eEfe495a360e0"
POOL = "0x8366a39cc670b4001a1121b8f6a443a643e40951"   # Uniswap v4 PoolManager
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
ZERO = "0x" + "0" * 40
DEAD = "0x000000000000000000000000000000000000dead"
GENESIS = 49_296_036

def rpc(method, params, tries=12):
    last = None
    for t in range(tries):
        url = RPCS[t % len(RPCS)]
        try:
            req = urllib.request.Request(url, data=json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(), headers=HDR)
            r = json.load(urllib.request.urlopen(req, timeout=90))
            if "error" in r:
                last = r["error"]; time.sleep(.6); continue
            return r["result"]
        except Exception as e:
            last = e; time.sleep(1.0 * (t + 1))
    raise RuntimeError(last)

def fetch_logs(addr, start, latest, step=250_000):
    out, b = [], start
    while b <= latest:
        e = min(b + step, latest)
        try:
            out += rpc("eth_getLogs", [{"address": addr, "fromBlock": hex(b),
                                        "toBlock": hex(e), "topics": [TRANSFER]}])
        except Exception:
            if step > 15_000:
                step //= 2; continue
            print("  skipped", b, e, flush=True)
        b = e + 1
        print(f"  {e}/{latest} n={len(out)}", flush=True)
    return out

def main():
    latest = int(rpc("eth_blockNumber", []), 16)
    print("latest block", latest, flush=True)
    logs = fetch_logs(V2, GENESIS, latest)
    logs.sort(key=lambda l: (int(l["blockNumber"], 16), int(l.get("logIndex", "0x0"), 16)))

    bal = collections.defaultdict(int)
    inflow_pool = collections.defaultdict(int)    # bought out of the pool
    outflow_pool = collections.defaultdict(int)   # sold into the pool
    out_other = collections.defaultdict(int)      # sent anywhere else
    minted, burned, mint_to = 0, 0, collections.defaultdict(int)

    for l in logs:
        f = "0x" + l["topics"][1][26:].lower()
        t = "0x" + l["topics"][2][26:].lower()
        v = int(l["data"], 16)
        if f == ZERO:
            minted += v; mint_to[t] += v
        else:
            bal[f] -= v
            if t == POOL: outflow_pool[f] += v
            else: out_other[f] += v
        if t in (ZERO, DEAD): burned += v
        if t != ZERO:
            bal[t] += v
            if f == POOL: inflow_pool[t] += v

    holders = {a: v for a, v in bal.items() if v > 0}
    supply = sum(holders.values())

    # never-sold accumulators: bought out of the pool, never sent a token anywhere
    cands = []
    for a, v in holders.items():
        if a in (POOL, ZERO, DEAD): continue
        if inflow_pool[a] > 0 and outflow_pool[a] == 0 and out_other[a] == 0:
            cands.append((a, v / 1e18, inflow_pool[a] / 1e18))
    cands.sort(key=lambda x: -x[1])

    code = {}
    for a, _, _ in cands[:12]:
        try: code[a] = len(rpc("eth_getCode", [a, "latest"])) > 4
        except Exception: code[a] = None

    out = {
        "block": latest,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "transfers": len(logs),
        "minted": minted / 1e18,
        "burned": burned / 1e18,
        "supply_from_logs": supply / 1e18,
        "mint_recipients": [[a, v / 1e18] for a, v in sorted(mint_to.items(), key=lambda x: -x[1])],
        "holders": len(holders),
        "pool_balance": holders.get(POOL, 0) / 1e18,
        "never_sold": [[a, b, i, code.get(a)] for a, b, i in cands[:12]],
        "never_sold_total": sum(c[1] for c in cands),
        "never_sold_count": len(cands),
        "v1_in_poolmanager": int(rpc("eth_call", [{"to": V1,
            "data": "0x70a08231000000000000000000000000" + POOL[2:]}, "latest"]), 16) / 1e18,
    }
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit.json")
    json.dump(out, open(path, "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ("never_sold", "mint_recipients")}, indent=1), flush=True)
    print("\nmint recipients:", out["mint_recipients"][:3], flush=True)
    print("\nnever-sold accumulators (top 12):", flush=True)
    for a, b, i, c in out["never_sold"]:
        print(f"  {a} bal={b:>16,.2f} bought={i:>16,.2f} {'contract' if c else 'wallet'}", flush=True)
    print("\nwrote", path, flush=True)

if __name__ == "__main__":
    main()
