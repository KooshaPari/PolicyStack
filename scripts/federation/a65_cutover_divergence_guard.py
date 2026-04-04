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
p=argparse.ArgumentParser(); p.add_argument('--metrics', required=True); p.add_argument('--max-divergence', type=float, default=0.0); a=p.parse_args()
m=load(a.metrics)
if float(m.get('cutover_divergence',m.get('divergence',0.0)))>a.max_divergence:
    print('A65 cutover divergence guard failed', file=sys.stderr); raise SystemExit(2)
