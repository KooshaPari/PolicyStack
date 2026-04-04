#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone
p=argparse.ArgumentParser(); p.add_argument('--attestations', required=True); p.add_argument('--min-days', type=int, default=7); a=p.parse_args()
items=json.loads(pathlib.Path(a.attestations).read_text()); now=datetime.now(timezone.utc)
for i in items:
    dt=datetime.fromisoformat(str(i['expires_at']).replace('Z','+00:00'))
    if (dt-now).total_seconds()<a.min_days*86400:
        print('B63 attestation expiry drift breach', file=sys.stderr); raise SystemExit(2)
