#!/bin/sh
set -e
echo "[1/4] holders";      python3 dump_holders.py
echo "[2/4] entitlements"; python3 dump_all.py
echo "[3/4] audit";        python3 onchain_audit.py
echo "[4/4] timeline";     python3 timeline.py
echo DONE_ALL
