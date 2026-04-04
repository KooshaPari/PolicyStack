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
    return str(r.get('id') or r.get('replay_id') or r.get('run_id') or '?').strip()


p = argparse.ArgumentParser()
p.add_argument('--latency-metrics', required=True)
p.add_argument('--replay-csv', required=True)
p.add_argument('--max-p95-ms', type=float, default=1200.0)
p.add_argument('--max-p99-ms', type=float, default=2500.0)
p.add_argument('--max-p95-breaches', type=int, default=0)
p.add_argument('--max-status-failures', type=int, default=0)
a = p.parse_args()

try:
    metrics = json.loads(pathlib.Path(a.latency_metrics).read_text())
except Exception:
    print('C81 invalid latency metrics JSON', file=sys.stderr)
    raise SystemExit(2)

rows = sorted(
    list(csv.DictReader(pathlib.Path(a.replay_csv).read_text().splitlines())),
    key=lambda r: json.dumps(r, sort_keys=True),
)

breaches = []
p95_json = _num(metrics.get('replay_p95_ms', metrics.get('p95_ms', 0.0)))
p99_json = _num(metrics.get('replay_p99_ms', metrics.get('p99_ms', 0.0)))
if p95_json > a.max_p95_ms:
    breaches.append('metrics:p95')
if p99_json > a.max_p99_ms:
    breaches.append('metrics:p99')
if int(metrics.get('p95_breaches', metrics.get('replay_p95_breaches', 0))) > a.max_p95_breaches:
    breaches.append('metrics:p95_breach_count')

fails = 0
for row in rows:
    rid = _row_id(row)
    if _num(row.get('p95_ms', 0.0)) > a.max_p95_ms:
        breaches.append(f'p95:{rid}')
    if _num(row.get('p99_ms', row.get('p99', 0.0))) > a.max_p99_ms:
        breaches.append(f'p99:{rid}')
    status = str(row.get('status', '')).strip().lower()
    if _truthy(row.get('breach', False)) or status in {'fail', 'failed', 'breach', 'timeout'}:
        fails += 1
        breaches.append(f'failure:{rid}')

if fails > a.max_status_failures:
    breaches.append(f'failure_count={fails}')

if breaches:
    print('C81 replay latency quantile breach: ' + ','.join(sorted(set(breaches))), file=sys.stderr)
    raise SystemExit(2)
