#!/usr/bin/env python3
"""Router-aware buy/sell attribution.

A transfer-level view mis-reads any trade routed through a contract: the tokens
move pool -> router -> trader, so only the router looks like it touched the pool.
This groups every V2 Transfer by transaction and nets each address inside it.
Routers and other pass-throughs net to zero and drop out on their own; what is
left is the address that actually gained or lost the tokens.

Writes flows.json.
"""
import json, urllib.request, time, collections

RPCS = ["https://robinhood-rpc.publicnode.com", "https://rpc.mainnet.chain.robinhood.com",
        "https://rpc.ordofi.network"]
HDR = {"content-type": "application/json", "user-agent": "Mozilla/5.0"}
V2 = "0x737054bd706cba68eaF4661411FeDE5F6C2952e5"
TR = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
PM = "0x8366a39cc670b4001a1121b8f6a443a643e40951"
HOOK = "0x332f85e7e323214b2d55286414b059ebb1f2a044"
ZERO = "0x" + "0" * 40
GENESIS = 49_296_036
# infrastructure that moves tokens without taking a market position
INFRA = {PM, HOOK, ZERO, "0x9310bc8bf95fa35608a9f08f76b55b4fdddc1ef0",
         "0x22e9504714c7cdfb464863d3c7df61b27b05ef79",
         "0xc47d65424d3c08eaf964fd96e67d0dfc58722a45"}

def rpc(method, params, tries=8):
    for t in range(tries):
        try:
            req = urllib.request.Request(RPCS[t % len(RPCS)], headers=HDR, data=json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode())
            r = json.load(urllib.request.urlopen(req, timeout=75))
            if "error" in r:
                time.sleep(.3); continue
            return r["result"]
        except Exception:
            time.sleep(.5 * (t + 1))
    return None

def main():
    latest = int(rpc("eth_blockNumber", []), 16)
    logs, b, step = [], GENESIS, 400_000
    while b <= latest:
        e = min(b + step, latest)
        r = rpc("eth_getLogs", [{"address": V2, "fromBlock": hex(b), "toBlock": hex(e), "topics": [TR]}])
        if r is None:
            if step > 15_000:
                step //= 2; continue
            b = e + 1; continue
        logs += r; b = e + 1
        print(f"  {e}/{latest} n={len(logs)}", flush=True)

    by_tx = collections.defaultdict(list)
    for l in logs:
        by_tx[l["transactionHash"]].append(l)

    bought = collections.Counter(); sold = collections.Counter()
    mint = collections.Counter(); routers = collections.Counter()
    hook_fee = 0.0; hook_sold = 0.0
    for tx, group in by_tx.items():
        delta = collections.defaultdict(float)
        for l in group:
            f = "0x" + l["topics"][1][26:].lower()
            t = "0x" + l["topics"][2][26:].lower()
            v = int(l["data"], 16) / 1e18
            if f == ZERO:
                mint[t] += v
            else:
                delta[f] -= v
            if t != ZERO:
                delta[t] += v
        pm = delta.get(PM, 0.0)
        if abs(pm) < 1e-9:
            continue
        hk = delta.get(HOOK, 0.0)
        if hk > 0: hook_fee += hk
        if hk < 0: hook_sold += -hk
        for a, d in delta.items():
            if a in INFRA or abs(d) < 1e-9:
                continue
            # a wallet that nets to ~0 inside the tx only passed tokens through
            if pm < 0 and d > 0: bought[a] += d
            elif pm > 0 and d < 0: sold[a] += -d
        # anything that both received and sent within the tx is a pass-through
        for l in group:
            f = "0x" + l["topics"][1][26:].lower()
            t = "0x" + l["topics"][2][26:].lower()
            if abs(delta.get(f, 0)) < 1e-9 and f not in INFRA: routers[f] += 1
            if abs(delta.get(t, 0)) < 1e-9 and t not in INFRA: routers[t] += 1

    out = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "block": latest, "transfers": len(logs), "txs": len(by_tx),
        "hookFeeAccrued": round(hook_fee, 2), "hookSold": round(hook_sold, 2),
        "totalBought": round(sum(bought.values()), 2), "totalSold": round(sum(sold.values()), 2),
        "flows": {a: [round(bought[a], 2), round(sold[a], 2)]
                  for a in set(list(bought) + list(sold)) if bought[a] or sold[a]},
        "mints": {a: round(v, 2) for a, v in mint.items()},
        "routers": [[a, n] for a, n in routers.most_common(10)],
    }
    json.dump(out, open("flows.json", "w"))
    print(f"\ntxs touching the pool: {len(by_tx):,}")
    print(f"bought {out['totalBought']:,.0f} | sold {out['totalSold']:,.0f}")
    print(f"hook fee accrued {out['hookFeeAccrued']:,.0f} | hook sold {out['hookSold']:,.0f}")
    print("\npass-through contracts (routers):", flush=True)
    for a, n in out["routers"][:5]:
        print(f"  {a}  {n} legs")
    print("\ntop net buyers:")
    net = sorted(((bought[a] - sold[a], a) for a in out["flows"]), reverse=True)
    for v, a in net[:10]:
        print(f"  {a} net {v:>+15,.0f}  (bought {bought[a]:,.0f} sold {sold[a]:,.0f})")
    print("\ntop net sellers:")
    for v, a in net[-10:]:
        print(f"  {a} net {v:>+15,.0f}  (bought {bought[a]:,.0f} sold {sold[a]:,.0f})")

if __name__ == "__main__":
    main()
