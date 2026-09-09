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
V2="0x737054bd706cba68eaF4661411FeDE5F6C2952e5"
PONS="0x39dBED3a2bd333467115dE45665cC57F813C4571"
PM="0x8366a39cc670b4001a1121b8f6a443a643e40951".lower()
TR="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
def pad32(a): return "0x000000000000000000000000"+a[2:].lower()
def bal(t,a):
    r=rpc("eth_call",[{"to":t,"data":"0x70a08231000000000000000000000000"+a[2:]},"latest"])
    return int(r,16)/1e18 if r and r!="0x" else 0
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
for U,label,start in [("0x5083727d6fa9a56ce5fbc4cdf672ec13ff0ed596","ALT (received 23.2M V1)",44_000_000),
                      ("0x70845f7978c3cd26a0bc8846933b8b490c556945","FUNDER of fomo wallet",44_000_000)]:
    code=rpc("eth_getCode",[U,"latest"]) or "0x"
    eth=int(rpc("eth_getBalance",[U,"latest"]),16)/1e18
    n=int(rpc("eth_getTransactionCount",[U,"latest"]),16)
    print(f"\n=== {label}\n    {U}",flush=True)
    print(f"    {'contract' if len(code)>4 else 'wallet'} ETH={eth:,.4f} txs={n} | V1={bal(V1,U):,.2f} V2={bal(V2,U):,.2f} PONS={bal(PONS,U):,.2f}",flush=True)
    for tok,name in ((V1,"V1"),(V2,"V2")):
        outs=scan(tok,[TR,pad32(U)],start); ins=scan(tok,[TR,None,pad32(U)],start)
        src=collections.Counter(); dst=collections.Counter(); fb={}
        for l in ins:  src["0x"+l["topics"][1][26:]]+=int(l["data"],16)
        for l in outs:
            d="0x"+l["topics"][2][26:]; dst[d]+=int(l["data"],16); fb.setdefault(d,int(l["blockNumber"],16))
        print(f"    --- {name}: {len(ins)} in / {len(outs)} out",flush=True)
        for a,v in src.most_common(5):
            print(f"       IN  {a} {v/1e18:>15,.2f}{'  <-- POOL' if a==PM else ''}",flush=True)
        for a,v in dst.most_common(6):
            c=rpc("eth_getCode",[a,"latest"]) or "0x"
            tag="POOL" if a==PM else ("contract" if len(c)>4 else "wallet")
            print(f"       OUT {a} {v/1e18:>15,.2f}  {tag} blk={fb[a]}",flush=True)
