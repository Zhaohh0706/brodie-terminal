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
PAD="0x9310bc8bf95fa35608a9f08f76b55b4fdddc1ef0"
r=rpc("eth_getTransactionReceipt",["0x1e4e9c646fec6edb58bfa2ced1c2611c5ea5fe44eeba8d259248cd42f03628e6"])
DEPT=[l["topics"][0] for l in r["logs"] if l["address"].lower()==PAD.lower()][0]
print("deposit event topic0:",DEPT,flush=True)
latest=int(rpc("eth_blockNumber",[]),16)
out=[];b=48_000_000;step=1_000_000
while b<=latest:
    e=min(b+step,latest)
    rr=rpc("eth_getLogs",[{"address":PAD,"fromBlock":hex(b),"toBlock":hex(e),"topics":[DEPT]}])
    if rr is None:
        if step>50_000: step//=2; continue
    else: out+=rr
    b=e+1
print("deposit events:",len(out),flush=True)
dep=collections.Counter(); ent=collections.Counter()
for l in out:
    who="0x"+l["topics"][1][26:]; d=l["data"][2:]
    dep[who]+=int(d[0:64],16); ent[who]+=int(d[64:128],16)
tD=sum(dep.values())/1e18; tE=sum(ent.values())/1e18
print(f"depositors {len(ent)} | V1 in {tD:,.2f} | V2 entitled {tE:,.2f} | ratio {tE/tD:.6f}",flush=True)
aud=json.load(open("audit.json")); mr={a.lower():v for a,v in aud["mint_recipients"]}
cl=un=0.0; unc=[]
for a,v in ent.items():
    e=v/1e18
    if mr.get(a.lower(),0)>0: cl+=e
    else: un+=e; unc.append((e,a))
print(f"\nMINTED at genesis : {cl:,.2f}  ({cl/(cl+un)*100:.1f}%)",flush=True)
print(f"NEVER minted      : {un:,.2f}  ({un/(cl+un)*100:.1f}%) across {len(unc)} addresses",flush=True)
unc.sort(reverse=True)
print("\nlargest never-minted entitlements:",flush=True)
for e,a in unc[:12]:
    tag="   <== UNIPCS ALT" if a.lower()=="0x5083727d6fa9a56ce5fbc4cdf672ec13ff0ed596" else ""
    print(f"   {a} {e:>16,.2f}{tag}",flush=True)
U="0x5083727d6fa9a56ce5fbc4cdf672ec13ff0ed596"
print(f"\nunipcs alt: deposited {dep.get(U,0)/1e18:,.2f} V1 -> entitled {ent.get(U,0)/1e18:,.2f} V2 | minted at genesis: {U in mr}",flush=True)
