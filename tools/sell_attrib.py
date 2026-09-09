#!/usr/bin/env python3
"""Who is actually selling BRODIE into the pool?
Splits every sell by the source of the seller's tokens: the fee hook, liquidity
operations, tokens received in the genesis mint (migration claims), or tokens
bought on the market. Writes sell_attrib.json."""
import json,urllib.request,time,collections
RPCS=["https://robinhood-rpc.publicnode.com","https://rpc.mainnet.chain.robinhood.com","https://rpc.ordofi.network"]
HDR={"content-type":"application/json","user-agent":"Mozilla/5.0"}
def rpc(m,p,tries=8):
    for t in range(tries):
        try:
            r=json.load(urllib.request.urlopen(urllib.request.Request(RPCS[t%len(RPCS)],
                data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),headers=HDR),timeout=70))
            if "error" in r: time.sleep(.3); continue
            return r["result"]
        except Exception: time.sleep(.5*(t+1))
    return None
V2="0x737054bd706cba68eaF4661411FeDE5F6C2952e5"
TR="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
PM="0x8366a39cc670b4001a1121b8f6a443a643e40951"
HOOK="0x332f85e7e323214b2d55286414b059ebb1f2a044"
LP={"0xc47d65424d3c08eaf964fd96e67d0dfc58722a45","0x22e9504714c7cdfb464863d3c7df61b27b05ef79",
    "0x9310bc8bf95fa35608a9f08f76b55b4fdddc1ef0"}
Z="0x"+"0"*40
latest=int(rpc("eth_blockNumber",[]),16)
logs=[];b=49_296_036;step=400_000
while b<=latest:
    e=min(b+step,latest)
    r=rpc("eth_getLogs",[{"address":V2,"fromBlock":hex(b),"toBlock":hex(e),"topics":[TR]}])
    if r is None:
        if step>15_000: step//=2; continue
        b=e+1; continue
    logs+=r; b=e+1
    print(f"  {e}/{latest} n={len(logs)}",flush=True)
mint=collections.Counter(); bought=collections.Counter(); sold=collections.Counter()
recvOther=collections.Counter()
for l in logs:
    f="0x"+l["topics"][1][26:].lower(); t="0x"+l["topics"][2][26:].lower(); v=int(l["data"],16)/1e18
    if f==Z: mint[t]+=v
    if f==PM and t!=PM: bought[t]+=v
    if t==PM and f!=PM: sold[f]+=v
    if f!=Z and f!=PM and t!=PM and t!=Z: recvOther[t]+=v
tot=sum(sold.values())
cat=collections.Counter(); detail=collections.defaultdict(list)
for a,s in sold.items():
    if a==HOOK: cat["fee_hook"]+=s; continue
    if a in LP: cat["liquidity"]+=s; continue
    m=mint.get(a,0.0); bq=bought.get(a,0.0); ro=recvOther.get(a,0.0)
    # attribute the sale to the token sources this wallet actually has, mint first
    fm=min(s,m); rest=s-fm
    fb=min(rest,bq); rest-=fb
    fo=min(rest,ro); rest-=fo
    cat["claim_dump"]+=fm; cat["round_trip"]+=fb; cat["received_then_sold"]+=fo; cat["unattributed"]+=rest
    if fm>0: detail["claim_dump"].append((a,fm,m))
top=sorted(detail["claim_dump"],key=lambda x:-x[1])[:20]
out={"generated":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"block":latest,
     "totalSold":tot,"categories":dict(cat),
     "topClaimDumpers":[[a,round(v,2),round(m,2)] for a,v,m in top],
     "sellers":len(sold)}
json.dump(out,open("sell_attrib.json","w"),indent=1)
print("\n=== SELL-SIDE ATTRIBUTION ===",flush=True)
print(f"total BRODIE sold into the pool: {tot:,.0f}  from {len(sold)} addresses",flush=True)
for k,v in cat.most_common():
    print(f"  {k:22} {v:>16,.0f}  {v/tot*100:6.2f}%",flush=True)
print("\ntop wallets selling tokens they were minted at genesis:",flush=True)
for a,v,m in top[:12]:
    print(f"  {a} sold {v:>14,.0f} of {m:>14,.0f} minted  ({v/m*100:5.1f}%)",flush=True)
