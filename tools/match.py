import json,urllib.request,time,collections
RPCS=["https://rpc.mainnet.chain.robinhood.com","https://robinhood-rpc.publicnode.com","https://rpc.arrowrpc.com","https://rpc.ordofi.network"]
HDR={"content-type":"application/json","user-agent":"Mozilla/5.0"}
def rpc(m,p,tries=8):
    last=None
    for t in range(tries):
        try:
            r=json.load(urllib.request.urlopen(urllib.request.Request(RPCS[t%len(RPCS)],
                data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),headers=HDR),timeout=60))
            if "error" in r: last=r["error"]; time.sleep(.25); continue
            return r["result"]
        except Exception as e: last=e; time.sleep(.4*(t+1))
    return None
V1="0x45F82AC5d507e988f7406935da8eEfe495a360e0"
PAD="0x9310bc8bf95fa35608a9f08f76b55b4fdddc1ef0"
TR="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
def pad32(a): return "0x000000000000000000000000"+a[2:].lower()
latest=int(rpc("eth_blockNumber",[]),16)
def scan(tok,topics,start,step=2_000_000):
    out=[];b=start
    while b<=latest:
        e=min(b+step,latest)
        r=rpc("eth_getLogs",[{"address":tok,"fromBlock":hex(b),"toBlock":hex(e),"topics":topics}])
        if r is None:
            if step>60_000: step//=2; continue
        else: out+=r
        b=e+1
    return out
dep=scan(V1,[TR,None,pad32(PAD)],44_000_000)
per=collections.Counter()
for l in dep: per["0x"+l["topics"][1][26:]]+=int(l["data"],16)
tot=sum(per.values())
print(f"V1 deposits into launchpad: {len(dep)} transfers from {len(per)} addresses, total {tot/1e18:,.2f}",flush=True)
aud=json.load(open("audit.json"))
mints={a.lower():v for a,v in aud["mint_recipients"]}
mint_nonpad=sum(v for a,v in mints.items() if a!=PAD.lower())
print(f"V2 minted to non-launchpad addresses: {mint_nonpad:,.2f} across {len(mints)-1}",flush=True)
ratio=mint_nonpad/(tot/1e18) if tot else 0
print(f"implied V2-per-V1 ratio: {ratio:.8f}\n",flush=True)
UN="0x5083727d6fa9a56ce5fbc4cdf672ec13ff0ed596"
d=per.get(UN,0)/1e18
print(f"unipcs alt deposit: {d:,.2f} V1  -> expected V2 ~{d*ratio:,.2f}\n",flush=True)
# find mint recipients whose amount is within 0.5% of expectation
tgt=d*ratio
cands=sorted(((abs(v-tgt)/tgt, a, v) for a,v in mints.items() if a!=PAD.lower()))[:8]
print("closest genesis-mint recipients to that expectation:",flush=True)
for err,a,v in cands:
    print(f"   {a} {v:>16,.2f}  err={err*100:6.3f}%",flush=True)
print("\ntop depositors vs their implied mint:",flush=True)
for a,v in per.most_common(12):
    exp=v/1e18*ratio
    best=min(((abs(mv-exp)/exp,ma,mv) for ma,mv in mints.items() if ma!=PAD.lower()))
    flag="   <== UNIPCS ALT" if a==UN else ""
    print(f"   dep {a} {v/1e18:>14,.2f} -> exp {exp:>14,.2f} | best {best[1]} {best[2]:>14,.2f} err={best[0]*100:5.2f}%{flag}",flush=True)
