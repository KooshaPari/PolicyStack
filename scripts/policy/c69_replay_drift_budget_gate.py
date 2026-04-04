#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _truthy(v): return str(v).strip().lower() in {'1','true','t','yes','y'}
def _rid(r): return str(r.get('id') or r.get('replay_id') or r.get('scenario') or '?').strip()

p=argparse.ArgumentParser(); p.add_argument('--metrics', required=True); p.add_argument('--drift-csv', required=True); p.add_argument('--max-drift-rate', type=float, default=0.0); p.add_argument('--max-drift-events', type=int, default=0); a=p.parse_args()
m=json.loads(pathlib.Path(a.metrics).read_text())
rows=sorted(list(csv.DictReader(pathlib.Path(a.drift_csv).read_text().splitlines())), key=lambda r: json.dumps(r, sort_keys=True))
b=[]
rate=float(m.get('replay_drift_rate', m.get('drift_rate', 0.0)) or 0.0)
events=int(m.get('replay_drift_events', m.get('drift_events', 0)) or 0)
if rate>a.max_drift_rate: b.append('drift_rate')
if events>a.max_drift_events: b.append('drift_events')
for r in rows:
    rr=float(r.get('drift_rate', r.get('rate', 0.0)) or 0.0)
    ev=int(r.get('drift_events', r.get('events', 0)) or 0)
    if _truthy(r.get('drift_breach')) or _truthy(r.get('breach')) or rr>a.max_drift_rate or ev>a.max_drift_events: b.append(f"replay:{_rid(r)}")
if b: print('C69 replay drift budget breach: '+','.join(sorted(set(b))), file=sys.stderr); raise SystemExit(2)
