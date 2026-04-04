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


def to_int(value, label):
    try:
        return int(float(str(value)))
    except Exception:
        print(f"A107 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def to_float(value, label):
    try:
        return float(str(value))
    except Exception:
        print(f"A107 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--evidence', required=True)
parser.add_argument('--max-backlog', type=int, default=0)
parser.add_argument('--min-success-ratio', type=float, default=0.99)
args = parser.parse_args()

rows = load_report(pathlib.Path(args.evidence))
if isinstance(rows, dict):
    backlog = to_int(rows.get('retarget_backlog', rows.get('backlog', 0)), 'retarget_backlog')
    success_ratio = to_float(rows.get('success_ratio', rows.get('completion_ratio', 1.0)), 'success_ratio')
else:
    backlog = 0
    success_ratio = 1.0
    for row in rows:
        backlog = max(backlog, to_int(row.get('retarget_backlog', row.get('backlog', 0)), 'retarget_backlog'))
        ratio = to_float(row.get('success_ratio', row.get('completion_ratio', 1.0)), 'success_ratio')
        success_ratio = min(success_ratio, ratio)

if backlog > args.max_backlog or success_ratio < args.min_success_ratio:
    print('A107 retargeting consistency gate failed', file=sys.stderr)
    raise SystemExit(2)
