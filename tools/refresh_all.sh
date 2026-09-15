#!/bin/sh
set -e
echo "[1/5] holders";      python3 dump_holders.py
echo "[2/5] entitlements"; python3 dump_all.py
echo "[3/5] audit";        python3 onchain_audit.py
echo "[4/5] timeline";     python3 timeline.py
echo "[5/5] sell-attrib"; python3 sell_attrib.py
echo DONE_ALL
