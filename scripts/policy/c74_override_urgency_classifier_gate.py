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


def _urgency(v):
    text = str(v or '').strip().lower()
    if text in {'critical', 'critical+urgent', 'p0', 'p1'}:
        return 4
    if text in {'urgent', 'high', 'p2'}:
        return 3
    if text in {'medium', 'normal', 'p3'}:
        return 2
    if text in {'low', 'p4'}:
        return 1
    return int(_num(v, 0))


def _oid(r):
    return str(r.get('id') or r.get('override_id') or r.get('name') or '?').strip()


p = argparse.ArgumentParser()
p.add_argument('--overrides', required=True)
p.add_argument('--override-csv', required=True)
p.add_argument('--max-urgent-overrides', type=int, default=0)
p.add_argument('--min-urgency-confidence', type=float, default=0.85)
a = p.parse_args()

overrides = json.loads(pathlib.Path(a.overrides).read_text())
rows = sorted(
    list(csv.DictReader(pathlib.Path(a.override_csv).read_text().splitlines())),
    key=lambda r: json.dumps(r, sort_keys=True),
)

if isinstance(overrides, dict):
    overrides = overrides.get('overrides', overrides.get('items', []))

urgent, bad_conf = 0, []
for item in overrides:
    if not _truthy(item.get('active', True)):
        continue
    if _urgency(item.get('urgency', item.get('urgency_level', 0))) >= 4:
        urgent += 1
    if _num(item.get('classifier_confidence', item.get('confidence', 1.0))) < a.min_urgency_confidence:
        bad_conf.append(_oid(item))

for row in rows:
    rid = _oid(row)
    if not _truthy(row.get('active', True)):
        continue
    if _urgency(row.get('urgency', row.get('urgency_level', 0))) >= 4:
        urgent += 1
    if _num(row.get('classifier_confidence', row.get('confidence', 1.0))) < a.min_urgency_confidence:
        bad_conf.append(rid)

msg = []
if urgent > a.max_urgent_overrides:
    msg.append(f'urgent_overrides={urgent}')
if bad_conf:
    msg.append('low_confidence='+','.join(sorted(set(bad_conf))))
if msg:
    print('C74 override urgency classifier breach: ' + '; '.join(msg), file=sys.stderr)
    raise SystemExit(2)
