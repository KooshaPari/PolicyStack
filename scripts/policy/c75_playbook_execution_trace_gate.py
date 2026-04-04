#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _truthy(v):
    return str(v).strip().lower() in {'1', 'true', 't', 'yes', 'y'}


def _num(v, default=0.0):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return float(default)


def _pid(r):
    return str(r.get('id') or r.get('playbook_id') or r.get('playbook') or '?').strip()


p = argparse.ArgumentParser()
p.add_argument('--playbooks', required=True)
p.add_argument('--execution-trace-csv', required=True)
p.add_argument('--max-failed-traces', type=int, default=0)
p.add_argument('--max-failure-rate', type=float, default=0.0)
a = p.parse_args()

playbooks = json.loads(pathlib.Path(a.playbooks).read_text())
rows = sorted(
    list(csv.DictReader(pathlib.Path(a.execution_trace_csv).read_text().splitlines())),
    key=lambda r: json.dumps(r, sort_keys=True),
)

if isinstance(playbooks, dict):
    playbooks = playbooks.get('playbooks', playbooks.get('items', []))

required = sorted(
    {
        str(x.get('id') or x.get('playbook_id') or x.get('name') or '').strip()
        for x in playbooks
        if x.get('required', True) is not False
    }
)

seen = set()
failed = []
duplicates = set()
covered = set()
for row in rows:
    pid = _pid(row)
    if pid in seen:
        duplicates.add(pid)
    seen.add(pid)
    status = str(row.get('status', '')).strip().lower()
    if status in {'fail', 'failed', 'error'} or _truthy(row.get('failed', False)):
        failed.append(pid)
    if _truthy(row.get('executed', row.get('complete', False))):
        covered.add(pid)

missing = sorted([x for x in required if x and x not in covered])
failed_unique = sorted(set(failed))
total = max(len(rows), 1)
fail_rate = len(failed_unique) / total

issues = []
if missing:
    issues.append('missing='+','.join(missing))
if duplicates:
    issues.append('duplicate='+','.join(sorted(duplicates)))
if failed_unique:
    issues.append('failed='+','.join(failed_unique))
if len(failed_unique) > a.max_failed_traces:
    issues.append(f'failed_count={len(failed_unique)}')
if fail_rate > a.max_failure_rate:
    issues.append(f'failure_rate={fail_rate:.6f}')

if issues:
    print('C75 playbook execution trace breach: ' + '; '.join(issues), file=sys.stderr)
    raise SystemExit(2)
