#!/usr/bin/env python3
"""Where did the fee ETH go?

Native ETH transfers leave no logs, and every public RPC on this chain gates
trace_* behind a paid key. What is still reachable: any *contract* the wallets
touched emits events that index them. Scanning by topic alone, with no address
filter, finds every such contract — bridges, wrappers, other tokens — which is
as far as the public data goes.
"""
import json, urllib.request, time, collections

# Only this node was verified to actually apply a topic filter when no address
# is given; another returned unfiltered logs, which silently poisons the scan.
RPCS = ["https://rpc.mainnet.chain.robinhood.com"]
HDR = {"content-type": "application/json", "user-agent": "Mozilla/5.0"}
WALLETS = {
    "0x28e35d8c909df0d084945e4d80b17dbd36b0e02c": "A 35% fee",
    "0x263ed295dafae1d9aadd6e56c4b6f9f38ee019dd": "B 30% Safe",
    "0xd64503dd73eb2a6f11856455e52bff8564172ef7": "C 21.6% fee",
    "0x2cf505f3cbb36e06d4bd4758d10716b5416baad0": "D 13.4% fee",
    "0x78655106b9c6261a33f23309040ed75a2315497e": "A sub-wallet",
}
START = 48_000_000
CHUNK = 200_000

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

def p32(a):
    return "0x000000000000000000000000" + a[2:].lower()

def main():
    latest = int(rpc("eth_blockNumber", []), 16)
    padded = [p32(a) for a in WALLETS]
    hits = []
    for slot in (1, 2):
        topics = [None, padded] if slot == 1 else [None, None, padded]
        b, step = START, CHUNK
        while b <= latest:
            e = min(b + step, latest)
            r = rpc("eth_getLogs", [{"fromBlock": hex(b), "toBlock": hex(e), "topics": topics}])
            if r is None:
                if step > 25_000:
                    step //= 2; continue
                b = e + 1; continue
            # never trust the node's filter — re-check every log locally
            want = set(WALLETS)
            for l in r:
                if any(("0x" + t[26:].lower()) in want for t in l["topics"][1:3]):
                    l["_slot"] = slot
                    hits.append(l)
            b = e + 1
            print(f"  slot{slot} {e}/{latest} hits={len(hits)}", flush=True)

    by_contract = collections.Counter()
    per_wallet = collections.defaultdict(collections.Counter)
    seen = set()
    for l in hits:
        key = (l["transactionHash"], l["logIndex"])
        if key in seen:
            continue
        seen.add(key)
        c = l["address"].lower()
        by_contract[c] += 1
        for t in l["topics"][1:3]:
            w = "0x" + t[26:].lower()
            if w in WALLETS:
                per_wallet[w][c] += 1
    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "block": latest,
           "contracts": by_contract.most_common(),
           "perWallet": {w: per_wallet[w].most_common() for w in WALLETS}}
    json.dump(out, open("fee_destination.json", "w"), indent=1)
    print(f"\nunique logs: {len(seen)}  contracts touched: {len(by_contract)}")
    for c, n in by_contract.most_common(20):
        code = rpc("eth_getCode", [c, "latest"]) or "0x"
        print(f"  {c}  x{n:<5} codeSize={(len(code)-2)//2}")
    print()
    for w, label in WALLETS.items():
        print(f"{label:14} {w}")
        for c, n in per_wallet[w].most_common(8):
            print(f"    {c} x{n}")

if __name__ == "__main__":
    main()
