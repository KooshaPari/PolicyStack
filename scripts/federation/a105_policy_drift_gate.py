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
        print(f"A105 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def to_int(value, label):
    try:
        return int(float(str(value)))
    except Exception:
        print(f"A105 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--report', required=True)
parser.add_argument('--max-drift', type=float, default=0.05)
parser.add_argument('--max-unexpected-entries', type=int, default=0)
args = parser.parse_args()

rows = load_report(pathlib.Path(args.report))
if isinstance(rows, dict):
    drift = to_float(rows.get('policy_drift', rows.get('drift', 0.0)), 'policy_drift')
    unexpected = to_int(rows.get('unexpected_entries', rows.get('unexpected_count', 0)), 'unexpected_entries')
else:
    drift = 0.0
    unexpected = 0
    for row in rows:
        drift = max(drift, to_float(row.get('policy_drift', row.get('drift', 0.0)), 'policy_drift'))
        unexpected += to_int(row.get('unexpected_entries', row.get('unexpected_count', 0)), 'unexpected_entries')

if drift > args.max_drift or unexpected > args.max_unexpected_entries:
    print('A105 policy drift gate failed', file=sys.stderr)
    raise SystemExit(2)
