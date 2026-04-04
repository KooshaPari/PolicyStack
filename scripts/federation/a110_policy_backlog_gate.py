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
        print(f"A110 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def to_float(value, label):
    try:
        return float(str(value))
    except Exception:
        print(f"A110 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--policy-report', required=True)
parser.add_argument('--max-backlog', type=int, default=0)
parser.add_argument('--min-fill-rate', type=float, default=0.99)
args = parser.parse_args()

rows = load_report(pathlib.Path(args.policy_report))
if isinstance(rows, dict):
    backlog = to_int(rows.get('policy_backlog', rows.get('backlog', 0)), 'policy_backlog')
    fill_rate = to_float(rows.get('fill_rate', rows.get('fill_ratio', 1.0)), 'fill_rate')
else:
    backlog = 0
    fill_rate = 1.0
    for row in rows:
        backlog = max(backlog, to_int(row.get('policy_backlog', row.get('backlog', 0)), 'policy_backlog'))
        fill_rate = min(fill_rate, to_float(row.get('fill_rate', row.get('fill_ratio', 1.0)), 'fill_rate'))

if backlog > args.max_backlog or fill_rate < args.min_fill_rate:
    print('A110 policy backlog gate failed', file=sys.stderr)
    raise SystemExit(2)
