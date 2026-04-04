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
    return str(v).strip().lower() in {'1', 'true', 't', 'yes', 'y'}


def _row_id(r):
    return str(
        r.get('id')
        or r.get('run_id')
        or r.get('replay_id')
        or r.get('playbook_id')
        or r.get('name')
        or '?'
    ).strip()


def _read_csv(path):
    rows = list(csv.DictReader(pathlib.Path(path).read_text().splitlines()))
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))


p = argparse.ArgumentParser()
p.add_argument('--backpressure-metrics', required=True)
p.add_argument('--replay-csv', required=True)
p.add_argument('--max-p95', type=float, default=0.75)
p.add_argument('--max-p99', type=float, default=0.9)
p.add_argument('--max-breaches', type=int, default=0)
p.add_argument('--max-stall-count', type=int, default=0)
a = p.parse_args()

try:
    metrics = json.loads(pathlib.Path(a.backpressure_metrics).read_text())
except Exception:
    print('C85 invalid backpressure metrics JSON', file=sys.stderr)
    raise SystemExit(2)

rows = _read_csv(a.replay_csv)
if not isinstance(metrics, dict):
    print('C85 backpressure metrics JSON must be an object', file=sys.stderr)
    raise SystemExit(2)

breaches = []

p95 = _num(metrics.get('replay_backpressure_p95', metrics.get('p95', 0.0)))
p99 = _num(metrics.get('replay_backpressure_p99', metrics.get('p99', 0.0)))
stall_count = int(_num(metrics.get('stall_count', metrics.get('backpressure_stalls', 0.0)))
breach_count = int(_num(metrics.get('breach_count', metrics.get('backpressure_breaches', 0.0)))
if p95 > a.max_p95:
    breaches.append('metrics:p95')
if p99 > a.max_p99:
    breaches.append('metrics:p99')
if breach_count > a.max_breaches:
    breaches.append('metrics:breach_count')
if stall_count > a.max_stall_count:
    breaches.append('metrics:stall_count')

for row in rows:
    rid = _row_id(row)
    if _num(row.get('backpressure_p95', row.get('p95', 0.0))) > a.max_p95:
        breaches.append(f'p95:{rid}')
    if _num(row.get('backpressure_p99', row.get('p99', 0.0))) > a.max_p99:
        breaches.append(f'p99:{rid}')
    status = str(row.get('status', '')).strip().lower()
    if _truthy(row.get('stalled', False)) or status in {'stalled', 'stuck', 'blocked', 'timeout'}:
        breaches.append(f'stall:{rid}')

if breaches:
    print('C85 replay backpressure quantile breach: ' + ','.join(sorted(set(breaches))), file=sys.stderr)
    raise SystemExit(2)
