#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _truthy(v):
    return str(v).strip().lower() in {'1', 'true', 't', 'yes', 'y'}


def _oid(r):
    return str(r.get('override_id') or r.get('id') or r.get('name') or '?').strip()


def _read_json(path, label):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except Exception:
        print(f'{label} invalid overrides JSON', file=sys.stderr)
        raise SystemExit(2)


def _read_csv(path):
    rows = list(csv.DictReader(pathlib.Path(path).read_text().splitlines()))
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))


p = argparse.ArgumentParser()
p.add_argument('--overrides', required=True)
p.add_argument('--reconciliation-csv', required=True)
p.add_argument('--max-unreconciled-overrides', type=int, default=0)
p.add_argument('--max-orphan-reconciliation-rows', type=int, default=0)
p.add_argument('--max-reconciliation-failures', type=int, default=0)
p.add_argument('--require-reconciled-at', action='store_true')
a = p.parse_args()

raw_overrides = _read_json(a.overrides, 'C94')
rows = _read_csv(a.reconciliation_csv)

if isinstance(raw_overrides, dict):
    overrides = raw_overrides.get('overrides', raw_overrides.get('items', []))
else:
    overrides = raw_overrides

if not isinstance(overrides, list):
    print('C94 overrides JSON must be a list', file=sys.stderr)
    raise SystemExit(2)

expected = set()
for item in overrides:
    if not isinstance(item, dict):
        continue
    if _truthy(item.get('active', True)) and str(item.get('id', '')).strip():
        expected.add(str(item.get('id')).strip())

reconciled = set()
seen = set()
duplicates = set()
failures = set()
missing_reconciled = []

for row in rows:
    oid = _oid(row)
    if not oid:
        continue
    if oid in seen:
        duplicates.add(oid)
    seen.add(oid)

    status = str(row.get('status', '')).strip().lower()
    if status in {'failed', 'error', 'timeout', 'mismatch'}:
        failures.add(oid)

    if _truthy(row.get('reconciled', row.get('matched', False))):
        if a.require_reconciled_at and not str(row.get('reconciled_at', '')).strip():
            failures.add(oid)
        reconciled.add(oid)
    else:
        reconciled_value = str(row.get('reconciled', '')).strip()
        if not reconciled_value or not _truthy(reconciled_value):
            if oid in expected:
                missing_reconciled.append(oid)

orphaned = set(seen) - expected
issues = []
if missing_reconciled:
    issues.append('unreconciled='+','.join(sorted(set(missing_reconciled))))
if duplicates:
    issues.append('duplicate='+','.join(sorted(duplicates)))
unreconciled_count = len(set(missing_reconciled))
if unreconciled_count > a.max_unreconciled_overrides:
    issues.append(f'unreconciled_count={unreconciled_count}')
if len(orphaned) > a.max_orphan_reconciliation_rows:
    issues.append('orphan_rows='+','.join(sorted(orphaned)))
if len(failures) > a.max_reconciliation_failures:
    issues.append(f'failures={len(failures)}')

if issues:
    print('C94 override reconciliation breach: ' + '; '.join(issues), file=sys.stderr)
    raise SystemExit(2)
