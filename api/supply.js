// Live BRODIE (V2) supply for CoinGecko / CoinMarketCap and anyone else who asks.
//
//   /supply/circulating   plain number      /supply/total   plain number
//   /supply/max           plain number      /api/supply     JSON with all three
//
// Circulating = total supply. V2 is minted only when a holder claims (unclaimed credits
// are not supply yet) and every burn() lowers totalSupply. There are no locked, vesting or
// treasury allocations; the vault and the migrator held 0 when checked on 2026-09-26.
//
// Listing sites poll this unattended, so an RPC hiccup must not turn into an error on their
// side: the read fails over to a second node, and a warm instance keeps its last good answer
// for up to an hour. The CDN caches every answer for 5 minutes, so most requests never get here.
const RPCS = ["https://rpc.mainnet.chain.robinhood.com", "https://robinhood-rpc.publicnode.com"];
const TOKEN = "0x737054bd706cba68eaF4661411FeDE5F6C2952e5";
const MAX_SUPPLY = 1000000000;
const KEEP_MS = 3600 * 1000;
let lastGood = null;                                         // { total, at } in this warm instance

async function totalSupplyFrom(url) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json", "user-agent": "Mozilla/5.0 (brodieonhood.com supply)" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "eth_call",
                           params: [{ to: TOKEN, data: "0x18160ddd" }, "latest"] }),
    signal: AbortSignal.timeout(5000),
  });
  if (!r.ok) throw new Error("rpc http " + r.status);
  const { result } = await r.json();
  if (!/^0x[0-9a-f]+$/i.test(result || "")) throw new Error("bad rpc answer");
  const total = Number(BigInt(result) / 10n ** 12n) / 1e6;   // 18 decimals, 6 kept
  if (!(total > 0 && total <= MAX_SUPPLY)) throw new Error("implausible supply " + total);
  return total;
}

async function totalSupply() {
  let last;
  for (const url of RPCS) {
    try {
      const total = await totalSupplyFrom(url);
      lastGood = { total, at: Date.now() };
      return { total, stale: false };
    } catch (e) { last = e; }
  }
  if (lastGood && Date.now() - lastGood.at < KEEP_MS) return { total: lastGood.total, stale: true };
  throw last;
}

module.exports = async (req, res) => {
  const q = String((req.query && req.query.q) || "").toLowerCase();
  res.setHeader("access-control-allow-origin", "*");
  if (q === "max") {
    res.setHeader("cache-control", "public, s-maxage=86400, stale-while-revalidate=604800");
    return res.status(200).send(String(MAX_SUPPLY));
  }
  try {
    const { total, stale } = await totalSupply();
    // a stale answer is cached briefly so the next request retries the chain soon
    res.setHeader("cache-control", stale ? "public, s-maxage=30" : "public, s-maxage=300, stale-while-revalidate=3600");
    if (stale) res.setHeader("x-supply-stale", "1");
    if (q === "total" || q === "circulating") return res.status(200).send(String(total));
    return res.status(200).json({
      token: TOKEN, chain: "Robinhood Chain", chain_id: 4663, decimals: 18,
      total_supply: total, circulating_supply: total, max_supply: MAX_SUPPLY,
      method: "totalSupply() read live; circulating equals total (no locked, vesting or treasury allocations; " +
              "unclaimed migration credits are not minted; burns reduce totalSupply)",
    });
  } catch (e) {
    res.setHeader("cache-control", "no-store");
    return res.status(502).send("supply unavailable, try again shortly");
  }
};
