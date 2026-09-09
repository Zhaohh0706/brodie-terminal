import json,urllib.request,time,collections
RPCS=["https://rpc.mainnet.chain.robinhood.com","https://robinhood-rpc.publicnode.com","https://rpc.ordofi.network"]
HDR={"content-type":"application/json","user-agent":"Mozilla/5.0"}
def rpc(m,p,tries=8):
    for t in range(tries):
        try:
            r=json.load(urllib.request.urlopen(urllib.request.Request(RPCS[t%len(RPCS)],
                data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),headers=HDR),timeout=60))
            if "error" in r: time.sleep(.3); continue
            return r["result"]
        except Exception: time.sleep(.5*(t+1))
    return None
PAD="0x9310bc8bf95fa35608a9f08f76b55b4fdddc1ef0"
DEPT="0x91ede45f04a37a7c170f5c1207df3b6bc748dc1e04ad5e917a241d0f52feada3"
latest=int(rpc("eth_blockNumber",[]),16)
out=[];b=48_000_000;step=1_000_000
while b<=latest:
    e=min(b+step,latest)
    r=rpc("eth_getLogs",[{"address":PAD,"fromBlock":hex(b),"toBlock":hex(e),"topics":[DEPT]}])
    if r is None:
        if step>50_000: step//=2; continue
        b=e+1; continue
    out+=r; b=e+1
dep=collections.Counter(); ent=collections.Counter()
for l in out:
    w="0x"+l["topics"][1][26:]; d=l["data"][2:]
    dep[w]+=int(d[0:64],16); ent[w]+=int(d[64:128],16)
aud=json.load(open("audit.json")); mr={a.lower():v for a,v in aud["mint_recipients"]}
unm={a:[round(dep[a]/1e18,2),round(v/1e18,2),1 if mr.get(a.lower(),0)>0 else 0] for a,v in ent.items()}
res={"generated":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"block":latest,
     "depositors":len(ent),"v1In":round(sum(dep.values())/1e18,2),"v2Entitled":round(sum(ent.values())/1e18,2),
     "count":len(unm),
     "all":dict(sorted(unm.items(),key=lambda x:-x[1][1]))}
json.dump(res,open("entitlements_all.json","w"),indent=1)
print(json.dumps({k:v for k,v in res.items() if k!="unminted"},indent=1))
print("rows:",len(unm))
for a,v in list(res["unminted"].items())[:70]: print(f"  {a} dep={v[0]:,.2f} ent={v[1]:,.2f}")
