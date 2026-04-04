#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys
def load(p):
    t=pathlib.Path(p).read_text()
    if str(p).lower().endswith('.csv'):
        r=list(csv.DictReader(t.splitlines())); return r[0] if r else {}
    return json.loads(t)
p=argparse.ArgumentParser(); p.add_argument('--evidence', required=True); p.add_argument('--min-ttl-seconds', type=int, default=1); p.add_argument('--max-expired', type=int, default=0); a=p.parse_args()
e=load(a.evidence)
ttl=int(float(e.get('ttl_seconds',e.get('evidence_ttl_seconds',0))))
expired=int(float(e.get('expired_count',e.get('expired',0))))
if ttl<a.min_ttl_seconds or expired>a.max_expired:
    print('A72 chaos evidence ttl gate failed', file=sys.stderr); raise SystemExit(2)
