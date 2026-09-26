// Live BRODIE (V2) supply for CoinGecko / CoinMarketCap and anyone else who asks.
//
//   /supply/circulating   plain number      /supply/total   plain number
//   /supply/max           plain number      /api/supply     JSON with all three
//
// Circulating = total supply. V2 is minted only when a holder claims (unclaimed credits
// are not supply yet) and every burn() lowers totalSupply. No team, treasury, vault or
// migrator wallet holds any: all were 0 when checked on 2026-09-26.
const RPC = "https://rpc.mainnet.chain.robinhood.com";
const TOKEN = "0x737054bd706cba68eaF4661411FeDE5F6C2952e5";
const MAX_SUPPLY = 1000000000;

async function totalSupply() {
  const r = await fetch(RPC, {
    method: "POST",
    headers: { "content-type": "application/json", "user-agent": "Mozilla/5.0 (brodieonhood.com supply)" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "eth_call",
                           params: [{ to: TOKEN, data: "0x18160ddd" }, "latest"] }),
    signal: AbortSignal.timeout(6000),
  });
  const { result } = await r.json();
  if (!/^0x[0-9a-f]+$/i.test(result || "")) throw new Error("bad rpc answer");
  return Number(BigInt(result) / 10n ** 12n) / 1e6;       // 18 decimals, 6 kept
}

module.exports = async (req, res) => {
  const q = String((req.query && req.query.q) || "").toLowerCase();
  try {
    const total = q === "max" ? null : await totalSupply();
    res.setHeader("cache-control", "public, s-maxage=300, stale-while-revalidate=3600");
    res.setHeader("access-control-allow-origin", "*");
    if (q === "max") return res.status(200).send(String(MAX_SUPPLY));
    if (q === "total" || q === "circulating") return res.status(200).send(String(total));
    return res.status(200).json({
      token: TOKEN, chain: "Robinhood Chain", chain_id: 4663, decimals: 18,
      total_supply: total, circulating_supply: total, max_supply: MAX_SUPPLY,
      method: "totalSupply() read live; circulating equals total (no locked, team or treasury balances; " +
              "unclaimed migration credits are not minted; burns reduce totalSupply)",
    });
  } catch (e) {
    res.setHeader("cache-control", "no-store");
    return res.status(502).send("supply unavailable, try again shortly");
  }
};
