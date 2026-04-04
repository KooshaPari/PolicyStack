#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone
p=argparse.ArgumentParser(); p.add_argument('--attestations', required=True); p.add_argument('--expires-key', default='expires_at'); p.add_argument('--now-utc', required=True); p.add_argument('--grace-hours', type=float, default=0.0); p.add_argument('--max-breaches', type=int, default=0); a=p.parse_args()
items=json.loads(pathlib.Path(a.attestations).read_text()); now=datetime.fromisoformat(a.now_utc.replace('Z','+00:00'))
if now.tzinfo is None: now=now.replace(tzinfo=timezone.utc)
grace=float(a.grace_hours)*3600.0
breaches=sum(1 for i in items if (now-datetime.fromisoformat(str(i[a.expires_key]).replace('Z','+00:00'))).total_seconds()>grace)
if breaches>a.max_breaches:
    print('B71 attestation grace window gate failed', file=sys.stderr); raise SystemExit(2)
