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


def _days_until(expiry, as_of):
    if not expiry:
        return None
    delta = expiry - as_of
    return delta.total_seconds() / 86400.0


def _oid(r):
    return str(r.get('id') or r.get('override_id') or r.get('name') or '?').strip()


p = argparse.ArgumentParser()
p.add_argument('--overrides', required=True)
p.add_argument('--override-csv', required=True)
p.add_argument('--as-of', required=True)
p.add_argument('--risk-window-days', type=float, default=7.0)
p.add_argument('--min-risk-score', type=float, default=0.8)
p.add_argument('--max-risky-overrides', type=int, default=0)
a = p.parse_args()

as_of = _ts(a.as_of)
if not as_of:
    print('C82 invalid --as-of timestamp', file=sys.stderr)
    raise SystemExit(2)

try:
    overrides = json.loads(pathlib.Path(a.overrides).read_text())
except Exception:
    print('C82 invalid overrides JSON', file=sys.stderr)
    raise SystemExit(2)

if isinstance(overrides, dict):
    overrides = overrides.get('overrides', overrides.get('items', []))

rows = sorted(
    list(csv.DictReader(pathlib.Path(a.override_csv).read_text().splitlines())),
    key=lambda r: json.dumps(r, sort_keys=True),
)

risky = set()
invalid = []
for override in overrides:
    if not _truthy(override.get('active', True)):
        continue
    rid = _oid(override)
    expiry = _ts(override.get('expires_at'))
    if not expiry:
        invalid.append(rid)
        continue
    days = _days_until(expiry, as_of)
    score = _num(override.get('risk_score', override.get('risk', 0.0)))
    if days < 0 or (days <= a.risk_window_days and score >= a.min_risk_score):
        risky.add(rid)

for row in rows:
    if not _truthy(row.get('active', True)):
        continue
    rid = _oid(row)
    expiry = _ts(row.get('expires_at'))
    if not expiry:
        invalid.append(rid)
        continue
    days = _days_until(expiry, as_of)
    score = _num(row.get('risk_score', row.get('risk', 0.0)))
    if days < 0 or (days <= a.risk_window_days and score >= a.min_risk_score):
        risky.add(rid)

msgs = []
if invalid:
    msgs.append('missing_or_invalid_expiry='+','.join(sorted(set(invalid))))
if len(risky) > a.max_risky_overrides:
    msgs.append(f'risky_overrides={len(risky)}')

if msgs:
    print('C82 override expiry risk breach: ' + '; '.join(msgs), file=sys.stderr)
    raise SystemExit(2)
