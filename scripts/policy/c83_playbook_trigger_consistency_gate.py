#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _truthy(v):
    return str(v).strip().lower() in {'1', 'true', 't', 'yes', 'y'}


def _pid(r):
    return str(r.get('playbook_id') or r.get('id') or r.get('name') or '?').strip()


def _tid(r):
    return str(r.get('trigger_id') or r.get('trigger') or r.get('name') or '?').strip()


p = argparse.ArgumentParser()
p.add_argument('--playbooks', required=True)
p.add_argument('--triggers-csv', required=True)
p.add_argument('--max-orphan-triggers', type=int, default=0)
p.add_argument('--max-failed-triggers', type=int, default=0)
p.add_argument('--max-missing-triggers', type=int, default=0)
a = p.parse_args()

try:
    playbooks = json.loads(pathlib.Path(a.playbooks).read_text())
except Exception:
    print('C83 invalid playbooks JSON', file=sys.stderr)
    raise SystemExit(2)

if isinstance(playbooks, dict):
    playbooks = playbooks.get('playbooks', playbooks.get('items', []))

required_pairs = set()
known_playbooks = set()
for pdef in playbooks:
    pid = _pid({'playbook_id': pdef.get('id') or pdef.get('playbook_id') or pdef.get('name')})
    if not pid:
        continue
    known_playbooks.add(pid)
    for tr in pdef.get('triggers', []) if isinstance(pdef.get('triggers', []), list) else []:
        tid = str(tr.get('id') or tr.get('trigger_id') or tr.get('name') or '').strip()
        required = _truthy(tr.get('required', True))
        if required and tid:
            required_pairs.add(f'{pid}::{tid}')

rows = sorted(
    list(csv.DictReader(pathlib.Path(a.triggers_csv).read_text().splitlines())),
    key=lambda r: json.dumps(r, sort_keys=True),
)

seen_pairs = set()
duplicates = set()
missing_required = []
failed = set()
orphans = set()

for row in rows:
    pair = f"{_pid(row)}::{_tid(row)}"
    if not pair.strip(':'):
        continue
    if pair in seen_pairs:
        duplicates.add(pair)
    seen_pairs.add(pair)
    status = str(row.get('status', '')).strip().lower()
    if _truthy(row.get('failed', False)) or status in {'failed', 'fail', 'error', 'mismatch'}:
        failed.add(pair)
    if pair not in required_pairs and pair not in orphans:
        orphans.add(pair)

missing = sorted(x for x in required_pairs if x.split('::')[0] in known_playbooks and x not in seen_pairs)
if not required_pairs:
    missing = []

if missing:
    missing_report = sorted(set(missing))
else:
    missing_report = []

if len(failed) > a.max_failed_triggers:
    fail_msg = {f'failed_count={len(failed)}'}
else:
    fail_msg = set()
issues = []
if missing_report:
    issues.append('missing='+','.join(sorted(missing_report)))
if duplicates:
    issues.append('duplicate='+','.join(sorted(duplicates)))
if fail_msg:
    issues.append(next(iter(fail_msg)))
if len(orphans) > a.max_orphan_triggers:
    issues.append(f'orphan_count={len(orphans)}')
if max(len(missing_report), 0) > a.max_missing_triggers:
    issues.append(f'missing_count={len(missing_report)}')

if issues:
    print('C83 playbook trigger consistency breach: ' + '; '.join(sorted(issues)), file=sys.stderr)
    raise SystemExit(2)
