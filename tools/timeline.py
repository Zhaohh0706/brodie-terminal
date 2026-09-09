#!/usr/bin/env python3
"""When did every fee sweep, payout and team buy actually happen?
Writes timeline.json: timestamped events for the hook, the splitter and the
four fee beneficiaries."""
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
HOOK="0x332f85e7e323214b2d55286414b059ebb1f2a044"
SPLIT="0xbc39b6502e1a6ab36e4a5c5026a35f08342a0a9c"
PM="0x8366a39cc670b4001a1121b8f6a443a643e40951"
ACC="0x4e45da441832cf53bdaa69235704fc0575e68210f459ee1562911024b12967d5"
TR="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TEAM=["0x28e35d8c909df0d084945e4d80b17dbd36b0e02c","0x263ed295dafae1d9aadd6e56c4b6f9f38ee019dd",
      "0xd64503dd73eb2a6f11856455e52bff8564172ef7","0x2cf505f3cbb36e06d4bd4758d10716b5416baad0"]
def p32(a): return "0x000000000000000000000000"+a[2:].lower()
latest=int(rpc("eth_blockNumber",[]),16)
def scan(addr,topics,start,step=1_000_000):
    out=[];b=start
    while b<=latest:
        e=min(b+step,latest)
        r=rpc("eth_getLogs",[{"address":addr,"fromBlock":hex(b),"toBlock":hex(e),"topics":topics}])
        if r is None:
            if step>40_000: step//=2; continue
        else: out+=r
        b=e+1
        print(f"  {e}/{latest} n={len(out)}",flush=True)
    return out
print("scanning splitter accruals…",flush=True)
acc=scan(SPLIT,[ACC],49_000_000)
print("scanning team buys…",flush=True)
buys={}
for t in TEAM:
    buys[t]=[l for l in scan(V2,[TR,p32(PM),p32(t)],49_296_036) ]
print("scanning hook sweeps…",flush=True)
sweeps=scan(V2,[TR,p32(HOOK),p32(PM)],49_296_036)

blocks=set()
for l in acc+sweeps: blocks.add(int(l["blockNumber"],16))
for t in TEAM:
    for l in buys[t]: blocks.add(int(l["blockNumber"],16))
print("resolving",len(blocks),"block timestamps…",flush=True)
ts={}
for i,b in enumerate(sorted(blocks)):
    r=rpc("eth_getBlockByNumber",[hex(b),False])
    if r: ts[b]=int(r["timestamp"],16)
    if i%50==0: print(f"   {i}/{len(blocks)}",flush=True)
def T(b): return ts.get(b,0)
ev=[]
for l in acc:
    b=int(l["blockNumber"],16)
    ev.append({"t":T(b),"blk":b,"kind":"payout","to":"0x"+l["topics"][1][26:],
               "hook":"0x"+l["topics"][2][26:],"eth":int(l["data"][2:66],16)/1e18,"tx":l["transactionHash"]})
for l in sweeps:
    b=int(l["blockNumber"],16)
    ev.append({"t":T(b),"blk":b,"kind":"sweep","tokens":int(l["data"],16)/1e18,"tx":l["transactionHash"]})
for t in TEAM:
    for l in buys[t]:
        b=int(l["blockNumber"],16)
        ev.append({"t":T(b),"blk":b,"kind":"buy","to":t,"tokens":int(l["data"],16)/1e18,"tx":l["transactionHash"]})
ev.sort(key=lambda e:(e["t"],e["blk"]))
json.dump({"generated":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"block":latest,"events":ev},
          open("timeline.json","w"))
print("events:",len(ev),"| payouts",sum(1 for e in ev if e['kind']=='payout'),
      "sweeps",sum(1 for e in ev if e['kind']=='sweep'),"buys",sum(1 for e in ev if e['kind']=='buy'),flush=True)
