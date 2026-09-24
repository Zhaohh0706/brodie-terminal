#!/usr/bin/env python3
"""
Brodie Burn Vault keeper. Polls windowState() (free) and sends burnNow() only
when the current bucket is open, so it never wastes gas on a closed window.
Runs fine from GitHub Actions every 15 minutes.

env:  VAULT_ADDRESS   deployed vault
      KEEPER_KEY      private key of a wallet holding a little ETH for gas ONLY
      RPC_URL         optional, defaults to the public Robinhood Chain RPC

Exit code is always 0: a closed window is not a failure.
"""
import os, sys, json, urllib.request
from eth_account import Account
from eth_utils import keccak, to_checksum_address
URL=os.environ.get('RPC_URL','https://rpc.mainnet.chain.robinhood.com'); CHAIN=4663
def rpc(m,p):
    r=urllib.request.Request(URL,data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),headers={'content-type':'application/json','user-agent':'brodie-keeper/1'})
    j=json.load(urllib.request.urlopen(r,timeout=60))
    if 'error' in j: raise RuntimeError(f"{m}: {j['error']}")
    return j['result']
vault=os.environ.get('VAULT_ADDRESS'); key=os.environ.get('KEEPER_KEY')
if not vault or not key: print("VAULT_ADDRESS / KEEPER_KEY not set, nothing to do"); sys.exit(0)
vault=to_checksum_address(vault)
sel=lambda s:'0x'+keccak(text=s)[:4].hex()
raw=rpc('eth_call',[{"to":vault,"data":sel('windowState()')},'latest'])[2:]
w=[int(raw[i:i+64],16) for i in range(0,len(raw),64)]
earliest,guaranteed,open_now,next_draw,tip=w
import time; now=int(time.time())
print(f"earliest {earliest-now:+d}s  guaranteed {guaranteed-now:+d}s  open={bool(open_now)}  nextDraw {next_draw-now:+d}s  tip={tip}bps")
if not open_now: print("window closed, skipping"); sys.exit(0)
acct=Account.from_key(key); me=acct.address
bal=int(rpc('eth_getBalance',[me,'latest']),16)
try:
    gas=int(rpc('eth_estimateGas',[{"from":me,"to":vault,"data":sel('burnNow()')}]),16)
except RuntimeError as e:
    print("estimateGas reverted (someone may have just burned, or below minimum):",str(e)[:160]); sys.exit(0)
gp=int(rpc('eth_gasPrice',[]),16)
# Self-funding: the vault pays its caller 0.5% only after 27 idle hours, so the
# keeper burns on time while it has gas, and when it runs low it waits for that
# tip window and refills from it. One burn's tip covers several calls.
limit, fee = int(gas*1.2), int(gp*1.25)
need = limit*fee                      # what the node checks before accepting the tx
if bal < need: print(f"keeper wallet {me} cannot afford one call ({bal/1e18:.8f} ETH) — top it up"); sys.exit(0)
if bal < need*4 and tip == 0:
    print(f"low on gas ({bal/1e18:.8f} ETH): waiting for the 0.5% tip window to refill"); sys.exit(0)
tx={"chainId":CHAIN,"nonce":int(rpc('eth_getTransactionCount',[me,'pending']),16),"gas":limit,
    "maxFeePerGas":fee,"maxPriorityFeePerGas":0,"to":vault,"value":0,"data":sel('burnNow()'),"type":2}
h=rpc('eth_sendRawTransaction',['0x'+acct.sign_transaction(tx).raw_transaction.hex()])
print("sent burnNow():",h)
