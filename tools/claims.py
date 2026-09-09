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
DEP="0x91ede45f04a37a7c0e5ad0e7a5b0b9d1e9a6ad9a"  # placeholder, real topic below
TOPIC=None
latest=int(rpc("eth_blockNumber",[]),16)
def scan(addr,topics,start,step=2_000_000):
    out=[];b=start
    while b<=latest:
        e=min(b+step,latest)
        r=rpc("eth_getLogs",[{"address":addr,"fromBlock":hex(b),"toBlock":hex(e),"topics":topics}])
        if r is None:
            if step>60_000: step//=2; continue
        else: out+=r
        b=e+1
    return out
allp=scan(PAD,[],44_000_000)
kinds=collections.Counter(l["topics"][0] for l in allp)
print("launchpad events by topic0:",flush=True)
for t,c in kinds.most_common(): print(f"   {t} x{c}",flush=True)
DEPT=[t for t,c in kinds.most_common() if t.startswith("0x91ede45f")]
DEPT=DEPT[0] if DEPT else None
ent=collections.Counter(); dep=collections.Counter()
for l in allp:
    if l["topics"][0]==DEPT and len(l["topics"])>1:
        who="0x"+l["topics"][1][26:]
        d=l["data"][2:]
        dep[who]+=int(d[0:64],16); ent[who]+=int(d[64:128],16)
print(f"\ndeposit events: {sum(1 for l in allp if l['topics'][0]==DEPT)} from {len(ent)} addresses",flush=True)
print(f"total V1 deposited : {sum(dep.values())/1e18:,.2f}",flush=True)
print(f"total V2 entitled  : {sum(ent.values())/1e18:,.2f}",flush=True)
print(f"implied ratio      : {sum(ent.values())/sum(dep.values()):.6f}",flush=True)
aud=json.load(open("audit.json"))
mr={a.lower():v for a,v in aud["mint_recipients"]}
claimed=unclaimed=0; unc=[]
for a,v in ent.items():
    e=v/1e18; m=mr.get(a.lower(),0)
    if m>0: claimed+=e
    else: unclaimed+=e; unc.append((e,a))
print(f"\nentitlements MINTED at genesis : {claimed:,.2f} ({claimed/(claimed+unclaimed)*100:.1f}%)",flush=True)
print(f"entitlements NOT minted        : {unclaimed:,.2f} ({unclaimed/(claimed+unclaimed)*100:.1f}%)  across {len(unc)} addresses",flush=True)
unc.sort(reverse=True)
print("\nlargest UNMINTED entitlements:",flush=True)
for e,a in unc[:15]:
    tag="  <== UNIPCS ALT" if a.lower()=="0x5083727d6fa9a56ce5fbc4cdf672ec13ff0ed596" else ""
    print(f"   {a} {e:>16,.2f}{tag}",flush=True)
U="0x5083727d6fa9a56ce5fbc4cdf672ec13ff0ed596"
print(f"\nunipcs alt entitlement: {ent.get(U,0)/1e18:,.4f} V2   minted? {U in mr}",flush=True)
for sig,name in [("0x70a08231","balanceOf"),("0x8b0e9f3f","?"),("0xfc0c546a","token"),("0x8da5cb5b","owner")]:
    r=rpc("eth_call",[{"to":PAD,"data":sig+("000000000000000000000000"+U[2:] if sig=="0x70a08231" else "")},"latest"])
    if r and r!="0x": print(f"   pad.{name} -> {r[:66]} ({int(r[:66],16)/1e18:,.4f})",flush=True)
json.dump({"entitlements":{a:str(v) for a,v in ent.items()}},open("entitlements.json","w"))
