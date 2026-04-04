#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone
p=argparse.ArgumentParser(); p.add_argument('--attestations', required=True); p.add_argument('--max-age-days', type=int, default=30); p.add_argument('--rotated-key', default='rotated_at'); a=p.parse_args()
items=json.loads(pathlib.Path(a.attestations).read_text()); now=datetime.now(timezone.utc)
for i in items:
    dt=datetime.fromisoformat(str(i[a.rotated_key]).replace('Z','+00:00'))
    if (now-dt).total_seconds()>a.max_age_days*86400:
        print('B67 attestation rotation SLA gate failed', file=sys.stderr); raise SystemExit(2)
