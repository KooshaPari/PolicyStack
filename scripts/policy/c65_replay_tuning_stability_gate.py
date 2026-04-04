#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _truthy(v): return str(v).strip().lower() in {'1','true','t','yes','y'}

p=argparse.ArgumentParser(); p.add_argument('--metrics', required=True); p.add_argument('--tuning-csv', required=True); p.add_argument('--max-loop-ms', type=float, default=500.0); p.add_argument('--max-instability-events', type=int, default=0); a=p.parse_args()
m=json.loads(pathlib.Path(a.metrics).read_text())
rows=sorted(list(csv.DictReader(pathlib.Path(a.tuning_csv).read_text().splitlines())), key=lambda r: json.dumps(r, sort_keys=True))
b=[]
if float(m.get('replay_loop_p95_ms',0.0))>a.max_loop_ms: b.append('replay_loop_p95_ms')
if int(m.get('instability_events',0))>a.max_instability_events: b.append('instability_events')
for r in rows:
    if str(r.get('status','')).strip().lower() in {'unstable','regressed','fail','failed'} or _truthy(r.get('breach','')): b.append(f"tuning:{r.get('profile') or r.get('scenario') or '?'}")
if b: print('C65 replay tuning stability breach: '+','.join(sorted(set(b))), file=sys.stderr); raise SystemExit(2)
