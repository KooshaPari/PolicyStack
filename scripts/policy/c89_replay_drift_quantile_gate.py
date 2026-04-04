#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys

def _num(v, default=0.0):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return float(default)

def _truthy(v):
    return str(v).strip().lower() in {'1','true','t','yes','y'}

def _rid(r):
    return str(r.get('id') or r.get('replay_id') or r.get('scenario') or '?').strip()

p=argparse.ArgumentParser()
p.add_argument('--drift-metrics', required=True)
p.add_argument('--drift-csv', required=True)
p.add_argument('--max-p95', type=float, default=0.90)
p.add_argument('--max-p99', type=float, default=0.98)
p.add_argument('--max-quantile-breaches', type=int, default=0)
p.add_argument('--max-failed-drift-rows', type=int, default=0)
a=p.parse_args()

try:
    metrics=json.loads(pathlib.Path(a.drift_metrics).read_text())
except Exception:
    print('C89 invalid drift metrics JSON', file=sys.stderr)
    raise SystemExit(2)

if not isinstance(metrics, dict):
    print('C89 drift metrics JSON must be an object', file=sys.stderr)
    raise SystemExit(2)

rows=sorted(list(csv.DictReader(pathlib.Path(a.drift_csv).read_text().splitlines())), key=lambda r: json.dumps(r, sort_keys=True))

breaches=[]
p95=_num(metrics.get('drift_p95', metrics.get('replay_drift_p95', 0.0)))
p99=_num(metrics.get('drift_p99', metrics.get('replay_drift_p99', 0.0)))
row_breaches=int(metrics.get('drift_quantile_breaches', metrics.get('quantile_breaches', 0.0)))
if p95>a.max_p95: breaches.append('metrics:p95')
if p99>a.max_p99: breaches.append('metrics:p99')
if row_breaches>a.max_quantile_breaches: breaches.append('metrics:quantile_breaches')

failed=0
for r in rows:
    rid=_rid(r)
    rp95=_num(r.get('drift_p95', r.get('p95', 0.0)))
    rp99=_num(r.get('drift_p99', r.get('p99', 0.0)))
    status=str(r.get('status','')).strip().lower()
    if rp95>a.max_p95: breaches.append(f'p95:{rid}')
    if rp99>a.max_p99: breaches.append(f'p99:{rid}')
    if _truthy(r.get('drift_breach', r.get('breach', False))) or status in {'breach','failed','fail'}:
        failed+=1
        breaches.append(f'failed:{rid}')

if failed>a.max_failed_drift_rows:
    breaches.append(f'failed_count={failed}')

if breaches:
    print('C89 replay drift quantile breach: '+','.join(sorted(set(breaches))), file=sys.stderr)
    raise SystemExit(2)
