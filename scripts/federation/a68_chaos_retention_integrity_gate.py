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
p=argparse.ArgumentParser(); p.add_argument('--evidence', required=True); p.add_argument('--min-retention-days', type=int, default=1); a=p.parse_args()
e=load(a.evidence)
if int(e.get('retention_days',0))<a.min_retention_days or not bool(e.get('integrity_ok',e.get('chain_complete',False))):
    print('A68 chaos retention integrity gate failed', file=sys.stderr); raise SystemExit(2)
