#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone
p=argparse.ArgumentParser(); p.add_argument('--attestations', required=True); p.add_argument('--min-hours', type=int, default=24); a=p.parse_args()
items=json.loads(pathlib.Path(a.attestations).read_text()); now=datetime.now(timezone.utc)
for i in items:
    dt=datetime.fromisoformat(str(i['updated_at']).replace('Z','+00:00'))
    if (now-dt).total_seconds()>a.min_hours*3600:
        print('E61 attestation freshness SLO breach', file=sys.stderr)
    raise SystemExit(2)
