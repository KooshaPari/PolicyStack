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
        print(f"A111 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def to_float(value, label):
    try:
        return float(str(value))
    except Exception:
        print(f"A111 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--relay-report', required=True)
parser.add_argument('--max-missing-paths', type=int, default=0)
parser.add_argument('--max-error-rate', type=float, default=0.01)
args = parser.parse_args()

rows = load_report(pathlib.Path(args.relay_report))
if isinstance(rows, dict):
    missing_paths = to_int(rows.get('missing_paths', rows.get('missing_path_count', 0)), 'missing_paths')
    error_rate = to_float(rows.get('error_rate', rows.get('failure_rate', 0.0)), 'error_rate')
else:
    missing_paths = 0
    error_rate = 0.0
    for row in rows:
        missing_paths = max(missing_paths, to_int(row.get('missing_paths', row.get('missing_path_count', 0)), 'missing_paths'))
        error_rate = max(error_rate, to_float(row.get('error_rate', row.get('failure_rate', 0.0)), 'error_rate'))

if missing_paths > args.max_missing_paths or error_rate > args.max_error_rate:
    print('A111 relay path integrity gate failed', file=sys.stderr)
    raise SystemExit(2)
