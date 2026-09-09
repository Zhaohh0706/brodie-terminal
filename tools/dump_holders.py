import json,urllib.request,time,collections
RPCS=["https://robinhood-rpc.publicnode.com","https://rpc.mainnet.chain.robinhood.com"]
HDR={"content-type":"application/json","user-agent":"Mozilla/5.0"}
def rpc(m,p,tries=10):
    for t in range(tries):
        try:
            r=json.load(urllib.request.urlopen(urllib.request.Request(RPCS[t%len(RPCS)],
                data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),headers=HDR),timeout=75))
            if "error" in r: time.sleep(.3); continue
            return r["result"]
        except Exception: time.sleep(.5*(t+1))
    return None
V2="0x737054bd706cba68eaF4661411FeDE5F6C2952e5"
TR="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
PM="0x8366a39cc670b4001a1121b8f6a443a643e40951"; Z="0x"+"0"*40
latest=int(rpc("eth_blockNumber",[]),16)
logs=[];b=49_296_036;step=400_000
while b<=latest:
    e=min(b+step,latest)
    r=rpc("eth_getLogs",[{"address":V2,"fromBlock":hex(b),"toBlock":hex(e),"topics":[TR]}])
    if r is None:
        if step>15_000: step//=2; continue
        b=e+1; continue
    logs+=r; b=e+1
    print(f'  {e}/{latest} n={len(logs)}',flush=True)
bal=collections.defaultdict(int); buy=collections.Counter(); sell=collections.Counter()
for l in logs:
    f="0x"+l["topics"][1][26:].lower(); t="0x"+l["topics"][2][26:].lower(); v=int(l["data"],16)
    if f!=Z: bal[f]-=v
    if t!=Z: bal[t]+=v
    if f==PM and t!=PM: buy[t]+=v
    if t==PM and f!=PM: sell[f]+=v
h={a:round(v/1e18,4) for a,v in bal.items() if v>0}
flows={a:[round(buy[a]/1e18,2),round(sell[a]/1e18,2)] for a in set(list(buy)+list(sell)) if buy[a] or sell[a]}
json.dump({"block":latest,"generated":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
           "transfers":len(logs),"holders":h,"flows":flows},open("holders_all.json","w"))
print("holders",len(h),"flows",len(flows),"block",latest,"transfers",len(logs))
