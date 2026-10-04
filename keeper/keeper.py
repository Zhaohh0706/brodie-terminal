#!/usr/bin/env python3
"""
Brodie Burn Vault keeper. Polls windowState() (free) and sends burnNow() only
when the current bucket is open, so it never wastes gas on a closed window.
Runs fine from GitHub Actions every 15 minutes.

env:  VAULT_ADDRESS   deployed vault
      KEEPER_KEY      private key of a wallet holding a little ETH for gas ONLY
      RPC_URL         optional, defaults to the public Robinhood Chain RPC

It also calls the token's renounceMinter() on its first poll after the minting
window closes (mintDeadline(), 2026-12-21 16:47:47 UTC).

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
TOKEN=to_checksum_address(os.environ.get('TOKEN_ADDRESS','0x737054bd706cba68eaF4661411FeDE5F6C2952e5'))
sel=lambda s:'0x'+keccak(text=s)[:4].hex()
word=lambda to,sig:int(rpc('eth_call',[{"to":to,"data":sel(sig)},'latest'])[2:66] or '0',16)
import time; now=int(time.time())
acct=Account.from_key(key); me=acct.address

def send(to,sig,label,reserve=1):
    """Sign and send a no-argument call. reserve = how many calls' worth of gas the
    wallet must hold first. Returns the tx hash, or None when it stood down."""
    bal=int(rpc('eth_getBalance',[me,'latest']),16)
    try:
        gas=int(rpc('eth_estimateGas',[{"from":me,"to":to,"data":sel(sig)}]),16)
    except RuntimeError as e:
        print(f"{label}: estimateGas reverted:",str(e)[:160]); return None
    gp=int(rpc('eth_gasPrice',[]),16)
    limit, fee = int(gas*1.2), int(gp*1.25)
    need = limit*fee                  # what the node checks before accepting the tx
    if bal < need: print(f"keeper wallet {me} cannot afford {label} ({bal/1e18:.8f} ETH) — top it up"); return None
    if bal < need*reserve:
        print(f"low on gas ({bal/1e18:.8f} ETH): waiting for the 0.5% tip window to refill"); return None
    tx={"chainId":CHAIN,"nonce":int(rpc('eth_getTransactionCount',[me,'pending']),16),"gas":limit,
        "maxFeePerGas":fee,"maxPriorityFeePerGas":0,"to":to,"value":0,"data":sel(sig),"type":2}
    return rpc('eth_sendRawTransaction',['0x'+acct.sign_transaction(tx).raw_transaction.hex()])

# The migrator stays the token's minter until mintDeadline(). After it, renounceMinter()
# is open to anyone and clears the minter for good, which is what turns scanners'
# is_mintable flag off. Nobody will remember the date, so the first poll past it calls it.
try:
    if now > word(TOKEN,'mintDeadline()') and word(TOKEN,'minter()'):
        h=send(TOKEN,'renounceMinter()','renounceMinter()')
        if h: print("sent renounceMinter():",h)
except Exception as e:
    print("renounceMinter check failed:",str(e)[:160])

raw=rpc('eth_call',[{"to":vault,"data":sel('windowState()')},'latest'])[2:]
w=[int(raw[i:i+64],16) for i in range(0,len(raw),64)]
earliest,guaranteed,open_now,next_draw,tip=w
print(f"earliest {earliest-now:+d}s  guaranteed {guaranteed-now:+d}s  open={bool(open_now)}  nextDraw {next_draw-now:+d}s  tip={tip}bps")
if not open_now: print("window closed, skipping"); sys.exit(0)
# Self-funding: the vault pays its caller 0.5% only after 27 idle hours, so the
# keeper burns on time while it has gas, and when it runs low it waits for that
# tip window and refills from it. One burn's tip covers several calls.
h=send(vault,'burnNow()','burnNow()',reserve=4 if tip == 0 else 1)
if h: print("sent burnNow():",h)
