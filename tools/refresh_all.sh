#!/bin/sh
# Local equivalent of .github/workflows/refresh-ledgers.yml. Run from tools/.
set -e
echo "[1/4] audit";        python3 onchain_audit.py
echo "[2/4] holders";      python3 dump_holders.py
echo "[3/4] entitlements"; python3 dump_all.py
echo "[4/4] fee timeline"; python3 timeline.py
cd .. && python3 scripts/inject.py && python3 scripts/smoke.py
echo DONE_ALL
