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
p=argparse.ArgumentParser(); p.add_argument('--health', required=True); p.add_argument('--min-recovery-budget', type=float, default=0.0); a=p.parse_args()
h=load(a.health)
if float(h.get('recovery_budget_remaining',h.get('recovery_budget',0.0)))<a.min_recovery_budget:
    print('A67 revocation recovery budget exhausted', file=sys.stderr); raise SystemExit(2)
