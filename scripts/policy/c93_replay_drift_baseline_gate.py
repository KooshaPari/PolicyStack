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


def _int(v, default=0):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return int(default)


def _truthy(v):
    return str(v).strip().lower() in {'1', 'true', 't', 'yes', 'y'}


def _rid(r):
    return str(r.get('id') or r.get('replay_id') or r.get('scenario') or '?').strip()


def _read_json(path, label):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except Exception:
        print(f'{label} invalid JSON', file=sys.stderr)
        raise SystemExit(2)


def _read_csv(path):
    rows = list(csv.DictReader(pathlib.Path(path).read_text().splitlines()))
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))


p = argparse.ArgumentParser()
p.add_argument('--baseline-metrics', required=True)
p.add_argument('--current-metrics', required=True)
p.add_argument('--drift-csv', required=True)
p.add_argument('--max-p95-degradation', type=float, default=0.02)
p.add_argument('--max-p99-degradation', type=float, default=0.02)
p.add_argument('--max-rate-degradation', type=float, default=0.0)
p.add_argument('--max-events-degradation', type=int, default=0)
p.add_argument('--max-breached-runs', type=int, default=0)
a = p.parse_args()

baseline = _read_json(a.baseline_metrics, 'C93 baseline')
current = _read_json(a.current_metrics, 'C93 current')
rows = _read_csv(a.drift_csv)

if not isinstance(baseline, dict):
    print('C93 baseline metrics must be an object', file=sys.stderr)
    raise SystemExit(2)
if not isinstance(current, dict):
    print('C93 current metrics must be an object', file=sys.stderr)
    raise SystemExit(2)

base_p95 = _num(baseline.get('replay_drift_p95', baseline.get('drift_p95', 0.0)))
base_p99 = _num(baseline.get('replay_drift_p99', baseline.get('drift_p99', 0.0)))
base_rate = _num(baseline.get('replay_drift_rate', baseline.get('drift_rate', 0.0)))
base_events = _int(baseline.get('replay_drift_events', baseline.get('drift_events', 0)))

cur_p95 = _num(current.get('replay_drift_p95', current.get('drift_p95', 0.0)))
cur_p99 = _num(current.get('replay_drift_p99', current.get('drift_p99', 0.0)))
cur_rate = _num(current.get('replay_drift_rate', current.get('drift_rate', 0.0)))
cur_events = _int(current.get('replay_drift_events', current.get('drift_events', 0)))

issues = []
if cur_p95 - base_p95 > a.max_p95_degradation:
    issues.append('metrics:p95')
if cur_p99 - base_p99 > a.max_p99_degradation:
    issues.append('metrics:p99')
if cur_rate - base_rate > a.max_rate_degradation:
    issues.append('metrics:drift_rate')
if cur_events - base_events > a.max_events_degradation:
    issues.append('metrics:drift_events')

breached_runs = 0
baseline_lookup = {
    _rid(r): {
        'p95': _num(r.get('baseline_p95', r.get('p95_baseline', r.get('p95', 0.0))), 0.0),
        'p99': _num(r.get('baseline_p99', r.get('p99_baseline', r.get('p99', 0.0))), 0.0),
        'rate': _num(r.get('baseline_rate', r.get('rate_baseline', 0.0))),
    }
    for r in rows
    if _rid(r)
}

for row in rows:
    rid = _rid(row)
    if _truthy(row.get('drift_breach')) or str(row.get('status', '')).strip().lower() in {'failed', 'breach', 'error'}:
        breached_runs += 1
        continue
    current_p95 = _num(row.get('drift_p95', row.get('p95', 0.0)))
    current_p99 = _num(row.get('drift_p99', row.get('p99', 0.0)))
    current_rate = _num(row.get('drift_rate', row.get('rate', 0.0)))
    baseline_row = baseline_lookup.get(rid)
    if baseline_row:
        if current_p95 - baseline_row['p95'] > a.max_p95_degradation:
            issues.append(f'p95:{rid}')
        if current_p99 - baseline_row['p99'] > a.max_p99_degradation:
            issues.append(f'p99:{rid}')
        if current_rate - baseline_row['rate'] > a.max_rate_degradation:
            issues.append(f'rate:{rid}')

if breached_runs > a.max_breached_runs:
    issues.append(f'breached_runs={breached_runs}')

if issues:
    print('C93 replay drift baseline breach: ' + '; '.join(sorted(set(issues))), file=sys.stderr)
    raise SystemExit(2)
