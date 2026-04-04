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


def _pid(r):
    return str(r.get('playbook_id') or r.get('id') or r.get('name') or '?').strip()


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
p.add_argument('--playbooks', required=True)
p.add_argument('--stability-csv', required=True)
p.add_argument('--max-overall-stability-score', type=float, default=0.90)
p.add_argument('--max-run-flakiness-rate', type=float, default=0.05)
p.add_argument('--max-flaky-runs', type=int, default=0)
p.add_argument('--max-failed-runs', type=int, default=0)
a = p.parse_args()

stats = _read_json(a.playbooks, 'C95 playbooks')
stability_rows = _read_csv(a.stability_csv)

if isinstance(stats, dict):
    playbook_defs = stats.get('playbooks', stats.get('items', []))
else:
    playbook_defs = stats

if not isinstance(playbook_defs, list):
    print('C95 playbooks JSON must be a list', file=sys.stderr)
    raise SystemExit(2)

baseline_score = _num(stats.get('playbook_stability_score', stats.get('stability_score', 1.0)), 1.0)
flaky_rate = _num(stats.get('playbook_flaky_run_rate', stats.get('flaky_rate', 0.0)), 0.0)
run_failures = _int(stats.get('playbook_failed_runs', stats.get('failed_runs', 0)), 0)

permitted_flaky = max(a.max_flaky_runs, 0)
permitted_failures = max(a.max_failed_runs, 0)
issues = []

if baseline_score < a.max_overall_stability_score:
    issues.append('overall_stability_score')
if flaky_rate > a.max_run_flakiness_rate:
    issues.append('flaky_run_rate')
if run_failures > a.max_failed_runs:
    issues.append(f'failed_runs={run_failures}')

expected = {}
for item in playbook_defs:
    if not isinstance(item, dict):
        continue
    expected[_pid(item)] = {
        'runs': _int(item.get('run_count', item.get('runs', 0))),
        'failures': _int(item.get('failed_runs', item.get('failures', 0))),
    }

flaky_runs = 0
bad_runs = set()
for row in stability_rows:
    pid = _pid(row)
    if _truthy(row.get('unstable', row.get('flaky', False))):
        flaky_runs += 1
        bad_runs.add(pid)
    status = str(row.get('status', '')).strip().lower()
    if status in {'failed', 'error', 'timeout', 'unstable'}:
        bad_runs.add(f'{pid}:status')
    run_count = _int(row.get('run_count', 0))
    failed = _int(row.get('failed_runs', row.get('failures', 0)))
    if run_count > 0 and failed > 0:
        ratio = failed / run_count
        limit = expected.get(pid, {}).get('runs', 1) or 1
        if ratio > a.max_run_flakiness_rate and run_count >= min(limit, 5):
            bad_runs.add(pid)

if flaky_runs > permitted_flaky:
    issues.append(f'flaky_runs={flaky_runs}')
if bad_runs and len(bad_runs) > permitted_failures:
    issues.append('unstable_playbooks=' + ','.join(sorted(bad_runs)))

if issues:
    print('C95 playbook stability breach: ' + '; '.join(sorted(set(issues))), file=sys.stderr)
    raise SystemExit(2)
