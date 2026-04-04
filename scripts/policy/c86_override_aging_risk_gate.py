#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
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


def _ts(v):
    s = str(v or '').strip().replace('Z', '+00:00')
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        return None


def _days(start, end):
    if not start or not end:
        return None
    return (end - start).total_seconds() / 86400.0


def _oid(r):
    return str(r.get('override_id') or r.get('id') or r.get('name') or '?').strip()


def _read_csv(path):
    rows = list(csv.DictReader(pathlib.Path(path).read_text().splitlines()))
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))


p = argparse.ArgumentParser()
p.add_argument('--overrides', required=True)
p.add_argument('--override-csv', required=True)
p.add_argument('--as-of', required=True)
p.add_argument('--max-aging-days', type=float, default=14.0)
p.add_argument('--min-risk-score', type=float, default=0.7)
p.add_argument('--max-risky-overrides', type=int, default=0)
p.add_argument('--max-missing-created', type=int, default=0)
a = p.parse_args()

as_of = _ts(a.as_of)
if not as_of:
    print('C86 invalid --as-of timestamp', file=sys.stderr)
    raise SystemExit(2)

try:
    overrides = json.loads(pathlib.Path(a.overrides).read_text())
except Exception:
    print('C86 invalid overrides JSON', file=sys.stderr)
    raise SystemExit(2)

if isinstance(overrides, dict):
    overrides = overrides.get('overrides', overrides.get('items', []))
if not isinstance(overrides, list):
    print('C86 overrides JSON must be a list', file=sys.stderr)
    raise SystemExit(2)

rows = _read_csv(a.override_csv)

active_ids = { _oid(r): r for r in rows if _truthy(r.get('active', True)) or str(r.get('active', '')).strip() == ''}
risky = set()
missing = []

for item in overrides:
    if not isinstance(item, dict):
        continue
    if not _truthy(item.get('active', True)):
        continue
    rid = _oid(item)
    created = _ts(item.get('created_at') or item.get('created'))
    if not created:
        missing.append(rid)
        continue
    age = _days(created, as_of)
    score = _num(item.get('risk_score', item.get('risk', 0.0)))
    if age is not None and age > a.max_aging_days and score >= a.min_risk_score:
        risky.add(rid)

for row in rows:
    if not _truthy(row.get('active', True)) and str(row.get('active', '')).strip() not in {'', '1'}:
        continue
    rid = _oid(row)
    created = _ts(row.get('created_at') or row.get('created'))
    if not created:
        missing.append(rid)
        continue
    age = _days(created, as_of)
    score = _num(row.get('risk_score', row.get('risk', 0.0)))
    if age is not None and age > a.max_aging_days and score >= a.min_risk_score:
        risky.add(rid)

issues = []
if missing:
    issues.append('missing_created=' + ','.join(sorted(set(missing))))
if len(risky) > a.max_risky_overrides:
    issues.append(f'risky_overrides={len(risky)}')

if issues:
    print('C86 override aging risk breach: ' + '; '.join(issues), file=sys.stderr)
    raise SystemExit(2)
