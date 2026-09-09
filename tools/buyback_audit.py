import json,urllib.request,time,collections
RPCS=["https://rpc.mainnet.chain.robinhood.com","https://robinhood-rpc.publicnode.com","https://rpc.arrowrpc.com","https://rpc.ordofi.network"]
HDR={"content-type":"application/json","user-agent":"Mozilla/5.0"}
def rpc(m,p,tries=10):
    last=None
    for t in range(tries):
        try:
            r=json.load(urllib.request.urlopen(urllib.request.Request(RPCS[t%len(RPCS)],
                data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),headers=HDR),timeout=75))
            if "error" in r: last=r["error"]; time.sleep(.3); continue
            return r["result"]
        except Exception as e: last=e; time.sleep(.5*(t+1))
    return None
V2="0x737054bd706cba68eaF4661411FeDE5F6C2952e5"
TR="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
PM="0x8366a39cc670b4001a1121b8f6a443a643e40951"
ZERO="0x"+"0"*40
TEAM={
 "0x28e35d8c909df0d084945e4d80b17dbd36b0e02c":"fee 35% wallet",
 "0x263ed295dafae1d9aadd6e56c4b6f9f38ee019dd":"fee 30% Safe 2/3",
 "0xd64503dd73eb2a6f11856455e52bff8564172ef7":"fee 21.6% wallet",
 "0x2cf505f3cbb36e06d4bd4758d10716b5416baad0":"fee 13.4% wallet",
 "0x332f85e7e323214b2d55286414b059ebb1f2a044":"v4 hook (fee sink)",
 "0x84b8affbd7728217f97c8eb47fe4bda07d97b8c1":"sweep operator / deployer",
 "0xbc39b6502e1a6ab36e4a5c5026a35f08342a0a9c":"fee splitter",
 "0x9310bc8bf95fa35608a9f08f76b55b4fdddc1ef0":"launchpad",
 "0x22e9504714c7cdfb464863d3c7df61b27b05ef79":"LP proxy",
 "0xc47d65424d3c08eaf964fd96e67d0dfc58722a45":"LP deployer",
 "0x1320a2b04a9e9ff511c7209c9669ebfe13cc818e":"Safe owner 1",
 "0x3825e7b3ff17637b08219e99d78b6c622b73f5b7":"Safe owner 2",
 "0xfa31fe751c203a623b52fad26b4063abc2ffdf50":"Safe owner 3",
}
latest=int(rpc("eth_blockNumber",[]),16)
logs=[];b=49_296_036;step=250_000
while b<=latest:
    e=min(b+step,latest)
    r=rpc("eth_getLogs",[{"address":V2,"fromBlock":hex(b),"toBlock":hex(e),"topics":[TR]}])
    if r is None:
        if step>15_000: step//=2; continue
        b=e+1; continue
    logs+=r; b=e+1
print("transfers:",len(logs),flush=True)
buy=collections.Counter(); sell=collections.Counter(); mint=collections.Counter(); bal=collections.defaultdict(int)
for l in logs:
    f="0x"+l["topics"][1][26:].lower(); t="0x"+l["topics"][2][26:].lower(); v=int(l["data"],16)
    if f==ZERO: mint[t]+=v
    else: bal[f]-=v
    if t!=ZERO: bal[t]+=v
    if f==PM and t!=PM: buy[t]+=v
    if t==PM and f!=PM: sell[f]+=v
supply=sum(v for v in bal.values() if v>0)/1e18
target=supply*0.006
print(f"supply {supply:,.2f} | 0.6% = {target:,.2f} BRODIE\n",flush=True)
print("=== TOP 15 BUYERS FROM THE POOL (all time, gross) ===",flush=True)
for a,v in buy.most_common(15):
    net=(v-sell[a])/1e18
    tag=TEAM.get(a,"")
    print(f"  {a} bought {v/1e18:>14,.2f} sold {sell[a]/1e18:>14,.2f} net {net:>14,.2f}  {'<<< '+tag if tag else ''}",flush=True)
print("\n=== TEAM-LINKED ADDRESSES: buy / sell / mint / balance ===",flush=True)
tb=ts=0
for a,label in TEAM.items():
    tb+=buy[a]; ts+=sell[a]
    print(f"  {label:26} {a}",flush=True)
    print(f"     bought {buy[a]/1e18:>14,.2f} | sold {sell[a]/1e18:>14,.2f} | genesis mint {mint[a]/1e18:>14,.2f} | now {max(bal[a],0)/1e18:>14,.2f}",flush=True)
print(f"\n  TEAM TOTAL bought {tb/1e18:,.2f}  sold {ts/1e18:,.2f}  NET {(tb-ts)/1e18:,.2f}",flush=True)
print(f"  as % of supply: gross {tb/1e18/supply*100:.4f}%  net {(tb-ts)/1e18/supply*100:.4f}%",flush=True)
print(f"  claim of 0.6% needs {target:,.2f} — shortfall {target-(tb-ts)/1e18:,.2f}",flush=True)
