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
PM="0x8366a39cc670b4001a1121b8f6a443a643e40951".lower()
TR="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
def pad32(a): return "0x000000000000000000000000"+a[2:].lower()
latest=int(rpc("eth_blockNumber",[]),16)
def scan(tok,topics,start,step=1_200_000):
    out=[];b=start
    while b<=latest:
        e=min(b+step,latest)
        r=rpc("eth_getLogs",[{"address":tok,"fromBlock":hex(b),"toBlock":hex(e),"topics":topics}])
        if r is None:
            if step>40_000: step//=2; continue
        else: out+=r
        b=e+1
    return out
ins=scan(V1,[TR,None,pad32(PM)],49_000_000)
print("V1->PoolManager txs:",len(ins),flush=True)
# per tx: V1 in, and V2 out to whom
mig=collections.Counter(); migV1=collections.Counter(); seen=set()
for i,l in enumerate(ins):
    h=l["transactionHash"]
    if h in seen: continue
    seen.add(h)
    r=rpc("eth_getTransactionReceipt",[h])
    if not r: continue
    v1in=sum(int(x["data"],16) for x in r["logs"]
             if x["address"].lower()==V1.lower() and x["topics"][0]==TR and "0x"+x["topics"][2][26:]==PM)
    for x in r["logs"]:
        if x["address"].lower()==V2.lower() and x["topics"][0]==TR and "0x"+x["topics"][1][26:]==PM:
            who="0x"+x["topics"][2][26:]
            if who!=PM:
                mig[who]+=int(x["data"],16); migV1[who]+=v1in
    if i%80==0: print(f"  {i}/{len(ins)}",flush=True)
print("\n=== migrators: received V2 out of the pool in a tx that put V1 in ===",flush=True)
rows=[]
for a,v in mig.most_common(25):
    code=rpc("eth_getCode",[a,"latest"]) or "0x"
    b2=rpc("eth_call",[{"to":V2,"data":"0x70a08231000000000000000000000000"+a[2:]},"latest"])
    bal=int(b2,16)/1e18 if b2 and b2!="0x" else 0
    kind="contract" if len(code)>4 else "wallet"
    rows.append((a,v/1e18,migV1[a]/1e18,bal,kind))
    print(f"  {a} gotV2={v/1e18:>14,.2f} paidV1={migV1[a]/1e18:>14,.2f} nowV2={bal:>14,.2f} {kind}",flush=True)
json.dump(rows,open("migrators.json","w"),indent=1)
print("saved migrators.json",flush=True)
