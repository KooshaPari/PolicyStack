#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def load_report(path):
    raw = path.read_text()
    if path.suffix.lower() == '.csv':
        return list(csv.DictReader(raw.splitlines()))
    return json.loads(raw)


def to_float(value, label):
    try:
        return float(str(value))
    except Exception:
        print(f"A109 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def to_int(value, label):
    try:
        return int(float(str(value)))
    except Exception:
        print(f"A109 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--sync-report', required=True)
parser.add_argument('--max-stale-age', type=float, default=900.0)
parser.add_argument('--max-stale-ratio', type=float, default=0.05)
args = parser.parse_args()

rows = load_report(pathlib.Path(args.sync_report))
if isinstance(rows, dict):
    max_stale_age = to_float(rows.get('max_stale_age', rows.get('stale_age', 0.0)), 'max_stale_age')
    stale_ratio = to_float(rows.get('stale_ratio', rows.get('ratio_stale', 0.0)), 'stale_ratio')
else:
    max_stale_age = 0.0
    stale_ratio = 0.0
    for row in rows:
        max_stale_age = max(max_stale_age, to_float(row.get('max_stale_age', row.get('stale_age', 0.0)), 'max_stale_age'))
        stale_ratio = max(stale_ratio, to_float(row.get('stale_ratio', row.get('ratio_stale', 0.0)), 'stale_ratio'))

if max_stale_age > args.max_stale_age or stale_ratio > args.max_stale_ratio:
    print('A109 sync age regression gate failed', file=sys.stderr)
    raise SystemExit(2)
