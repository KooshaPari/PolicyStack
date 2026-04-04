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
        print(f"A108 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def to_int(value, label):
    try:
        return int(float(str(value)))
    except Exception:
        print(f"A108 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--telemetry', required=True)
parser.add_argument('--max-error-rate', type=float, default=0.02)
parser.add_argument('--max-timeout-count', type=int, default=0)
args = parser.parse_args()

rows = load_report(pathlib.Path(args.telemetry))
if isinstance(rows, dict):
    error_rate = to_float(rows.get('error_rate', rows.get('failure_rate', 0.0)), 'error_rate')
    timeouts = to_int(rows.get('timeout_count', rows.get('timeouts', 0)), 'timeout_count')
else:
    error_rate = 0.0
    timeouts = 0
    if rows:
        counts = []
        for row in rows:
            counts.append(to_float(row.get('error_rate', row.get('failure_rate', 0.0)), 'error_rate'))
            timeouts += to_int(row.get('timeout_count', row.get('timeouts', 0)), 'timeout_count')
        error_rate = max(counts) if counts else 0.0

if error_rate > args.max_error_rate or timeouts > args.max_timeout_count:
    print('A108 telemetry reliability gate failed', file=sys.stderr)
    raise SystemExit(2)
