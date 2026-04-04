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


def _pid(r):
    return str(r.get('playbook_id') or r.get('id') or r.get('name') or '?').strip()


def _row_id(r):
    return str(r.get('run_id') or r.get('id') or r.get('name') or '?').strip()


def _read_csv(path):
    rows = list(csv.DictReader(pathlib.Path(path).read_text().splitlines()))
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))


p = argparse.ArgumentParser()
p.add_argument('--playbooks', required=True)
p.add_argument('--runs-csv', required=True)
p.add_argument('--default-timeout-ms', type=float, default=2000.0)
p.add_argument('--max-timeout-failures', type=int, default=0)
p.add_argument('--max-absent-playbooks', type=int, default=0)
a = p.parse_args()

try:
    playbooks = json.loads(pathlib.Path(a.playbooks).read_text())
except Exception:
    print('C87 invalid playbooks JSON', file=sys.stderr)
    raise SystemExit(2)

if isinstance(playbooks, dict):
    playbooks = playbooks.get('playbooks', playbooks.get('items', []))

if not isinstance(playbooks, list):
    print('C87 playbooks JSON must be a list', file=sys.stderr)
    raise SystemExit(2)

timeouts = {}
for pdef in playbooks:
    if not isinstance(pdef, dict):
        continue
    pid = _pid(pdef)
    timeouts[pid] = _num(pdef.get('timeout_ms', pdef.get('timeout', a.default_timeout_ms)))

rows = _read_csv(a.runs_csv)
timeouts_breached = set()
unknown_playbooks = set()
for row in rows:
    pid = _pid(row)
    rid = _row_id(row)
    if pid not in timeouts:
        unknown_playbooks.add(pid)
        continue
    limit = _num(row.get('timeout_ms', timeouts.get(pid, a.default_timeout_ms)))
    elapsed = _num(row.get('duration_ms', row.get('elapsed_ms', row.get('runtime_ms', 0.0))))
    status = str(row.get('status', '')).strip().lower()
    if elapsed > limit or status in {'timeout', 'timed_out', 'timed out', 'exceeded'}:
        timeouts_breached.add(f'{pid}:{rid}')

issues = []
if len(unknown_playbooks) > a.max_absent_playbooks:
    issues.append(f'unknown_playbook_count={len(unknown_playbooks)}')
if len(timeouts_breached) > a.max_timeout_failures:
    issues.append(f'timeout_failures={len(timeouts_breached)}')

if issues:
    print('C87 playbook timeout breach: ' + '; '.join(sorted(set(issues))), file=sys.stderr)
    raise SystemExit(2)
