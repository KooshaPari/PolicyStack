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
        print(f"A112 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def to_int(value, label):
    try:
        return int(float(str(value)))
    except Exception:
        print(f"A112 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--continuity-report', required=True)
parser.add_argument('--min-continuity-ratio', type=float, default=0.995)
parser.add_argument('--max-gap-count', type=int, default=0)
args = parser.parse_args()

rows = load_report(pathlib.Path(args.continuity_report))
if isinstance(rows, dict):
    continuity = to_float(rows.get('continuity_ratio', rows.get('continuity', 1.0)), 'continuity')
    gap_count = to_int(rows.get('continuity_gap_count', rows.get('gap_count', 0)), 'continuity_gap_count')
else:
    continuity = 1.0
    gap_count = 0
    for row in rows:
        continuity = min(continuity, to_float(row.get('continuity_ratio', row.get('continuity', 1.0)), 'continuity'))
        gap_count = max(gap_count, to_int(row.get('continuity_gap_count', row.get('gap_count', 0)), 'continuity_gap_count'))

if continuity < args.min_continuity_ratio or gap_count > args.max_gap_count:
    print('A112 cutover continuity gate failed', file=sys.stderr)
    raise SystemExit(2)
