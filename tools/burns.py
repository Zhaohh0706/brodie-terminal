#!/usr/bin/env python3
"""Write burns.json: every Burned event of the vault, with block times, plus the
vault's totals and whether it is still the creator-fee recipient.

scripts/inject.py folds this into data/tl.json, so the page can paint the burn
panel from the last ledger run before its own chain read lands, and keep
showing it (marked as a snapshot) if the RPC is down. Small and fast: one
topic-filtered eth_getLogs from the vault's deploy block, a handful of reads.
"""
import json, sys, time, urllib.request

RPC = "https://rpc.mainnet.chain.robinhood.com"
HDR = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 brodie-terminal ledger"}
VAULT = "0xC0f342a8936755697C535F1e8E0D712a8da672f8"
HOOK = "0x332F85E7e323214B2D55286414B059ebB1F2A044"
POOL_ID = "0xb6eae9d1f1838c4302d500e80d7aa854e45a6455f502215c7b970745b62d4b76"
VAULT_BLOCK = 69_411_335
BURNED = "0x4f5ba10edc95df02ea0e13cf2674a877b4061ae47073b4e760f4ec1be5d27b9e"   # Burned(seq,ethSpent,tokensBurned,spotWad,fillWad,emaWad,fracBps,cappedByDepth,caller)
SEL = {"totalBurned": "0xd89135cd", "totalEthSpent": "0x92d3b886", "burnCount": "0x524773ce", "hookPoolRecord": "0xad091230"}


def rpc(m, p, tries=6):
    last = None
    for i in range(tries):
        try:
            r = urllib.request.Request(RPC, json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(), HDR)
            j = json.load(urllib.request.urlopen(r, timeout=70))
            if "error" in j:
                raise RuntimeError(j["error"])
            return j["result"]
        except Exception as e:          # 429s and timeouts: back off and retry
            last = e
            time.sleep(1.5 * (i + 1))
    raise SystemExit("rpc %s failed: %s" % (m, last))


def call(to, data):
    return rpc("eth_call", [{"to": to, "data": data}, "latest"])


def wad(h):
    return int(h, 16) / 1e18


def word(data, i):
    return "0x" + data[2 + i * 64: 2 + (i + 1) * 64]


latest = int(rpc("eth_blockNumber", []), 16)
logs = []
b = VAULT_BLOCK
while b <= latest:                       # one call normally; smaller steps only if the node balks
    e = min(b + 8_000_000, latest)
    logs += rpc("eth_getLogs", [{"address": VAULT, "fromBlock": hex(b), "toBlock": hex(e), "topics": [BURNED]}])
    b = e + 1

burns = []
for l in sorted(logs, key=lambda l: int(l["topics"][1], 16)):
    blk = int(l["blockNumber"], 16)
    t = int(rpc("eth_getBlockByNumber", [hex(blk), False])["timestamp"], 16)
    d = l["data"]
    burns.append({
        "seq": int(l["topics"][1], 16), "t": t, "blk": blk, "tx": l["transactionHash"],
        "caller": "0x" + l["topics"][2][26:],
        "eth": round(wad(word(d, 0)), 9), "tokens": round(wad(word(d, 1)), 4),
        "spot": wad(word(d, 2)), "fill": wad(word(d, 3)), "ema": wad(word(d, 4)),
        "frac": int(word(d, 5), 16), "capped": int(word(d, 6), 16) == 1,
    })

# the hook's pool record keeps the live creator recipient in word 4
rec = call(HOOK, SEL["hookPoolRecord"] + POOL_ID[2:])
recipient = "0x" + rec[2 + 4 * 64 + 24: 2 + 5 * 64] if rec and len(rec) >= 2 + 5 * 64 else None
out = {
    "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "block": latest,
    "recipient": recipient, "isRecipient": bool(recipient) and recipient.lower() == VAULT.lower(),
    "totalBurned": wad(call(VAULT, SEL["totalBurned"])), "totalEth": wad(call(VAULT, SEL["totalEthSpent"])),
    "count": int(call(VAULT, SEL["burnCount"]), 16), "burns": burns,
}
if out["count"] != len(burns):
    sys.exit("vault says %d burns, found %d Burned events" % (out["count"], len(burns)))
json.dump(out, open("burns.json", "w"), separators=(",", ":"))
print("burns.json: %d burns, %.4f ETH → %.2f BRODIE, recipient %s, block %d"
      % (out["count"], out["totalEth"], out["totalBurned"], "vault" if out["isRecipient"] else recipient, latest))
