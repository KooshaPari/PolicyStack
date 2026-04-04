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
        print(f"A106 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def to_float(value, label):
    try:
        return float(str(value))
    except Exception:
        print(f"A106 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--schema-report', required=True)
parser.add_argument('--min-stability-ratio', type=float, default=0.98)
parser.add_argument('--max-regressions', type=int, default=0)
args = parser.parse_args()

rows = load_report(pathlib.Path(args.schema_report))
if isinstance(rows, dict):
    stability = to_float(rows.get('schema_stability', rows.get('stability_ratio', 1.0)), 'schema_stability')
    regressions = to_int(rows.get('regression_count', rows.get('regressions', 0)), 'regression_count')
else:
    stability = 1.0
    regressions = 0
    for row in rows:
        stability = min(stability, to_float(row.get('schema_stability', row.get('stability_ratio', 1.0)), 'schema_stability'))
        regressions += to_int(row.get('regression_count', row.get('regressions', 0)), 'regression_count')

if stability < args.min_stability_ratio or regressions > args.max_regressions:
    print('A106 schema stability gate failed', file=sys.stderr)
    raise SystemExit(2)
