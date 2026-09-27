#!/usr/bin/env python3
"""Write market.json: the pool's price, liquidity, volume and trade counts right now.

scripts/inject.py folds this into data/tl.json. The page reads DexScreener live;
this is only what it shows, marked as a snapshot, when neither DexScreener nor
GeckoTerminal can be reached from the reader's browser. Before this existed the
fallback was a price hard-coded on 24 September, off by 2x three days later.
Never fails the ledger job: no answer means no file, and the page keeps its own.
"""
import json, time, urllib.request

V2 = "0x737054bd706cba68eaF4661411FeDE5F6C2952e5"
HDR = {"User-Agent": "Mozilla/5.0 brodie-terminal ledger", "Accept": "application/json"}


def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=20))


try:
    pairs = get("https://api.dexscreener.com/latest/dex/tokens/" + V2).get("pairs") or []
    pairs = [p for p in pairs if p.get("chainId") == "robinhood" and p.get("baseToken", {}).get("address", "").lower() == V2.lower()
             and p.get("quoteToken", {}).get("symbol", "").upper() in ("ETH", "WETH")]
    p = max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
    t = p.get("txns") or {}
    side = lambda k: [(t.get(k) or {}).get("buys", 0), (t.get(k) or {}).get("sells", 0)]
    out = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "price": float(p["priceUsd"]), "priceNative": float(p["priceNative"]),
        "ch": {k: (p.get("priceChange") or {}).get(k, 0) for k in ("h1", "h6", "h24")},
        "liq": {k: (p.get("liquidity") or {}).get(k, 0) for k in ("usd", "base", "quote")},
        "vol": {k: (p.get("volume") or {}).get(k, 0) for k in ("m5", "h1", "h6", "h24")},
        "txns": {k: side(k) for k in ("m5", "h1", "h6", "h24")},
        "mcap": p.get("marketCap") or p.get("fdv") or 0,
        "createdAt": p.get("pairCreatedAt"),
    }
    json.dump(out, open("market.json", "w"), separators=(",", ":"))
    print("market: $%.10f · mcap $%s · liq $%s" % (out["price"], round(out["mcap"]), round(out["liq"]["usd"])))
except Exception as e:
    print("market snapshot skipped:", e)
