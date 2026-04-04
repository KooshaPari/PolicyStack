#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
from typing import Any


def load_report(path: pathlib.Path) -> list[dict[str, Any]] | dict[str, Any]:
    raw = path.read_text()
    if path.suffix.lower() == '.csv':
        return list(csv.DictReader(raw.splitlines()))
    return json.loads(raw)


def parse_float(value: object, label: str) -> float:
    try:
        return float(str(value))
    except Exception:
        print(f"A116 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"A116 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--retarget-report', required=True)
parser.add_argument('--min-retarget-ratio', type=float, default=0.96)
parser.add_argument('--max-fallbacks', type=int, default=0)
args = parser.parse_args()

rows = load_report(pathlib.Path(args.retarget_report))
if isinstance(rows, dict):
    retarget_ratio = parse_float(rows.get('retarget_ratio', rows.get('match_ratio', 1.0)), 'retarget_ratio')
    fallback_count = parse_int(rows.get('fallback_count', rows.get('fallbacks', 0)), 'fallback_count')
else:
    retarget_ratio = 1.0
    fallback_count = 0
    for row in rows:
        if row is None:
            continue
        retarget_ratio = min(retarget_ratio, parse_float(row.get('retarget_ratio', row.get('match_ratio', 1.0)), 'retarget_ratio'))
        fallback_count += parse_int(row.get('fallback_count', row.get('fallbacks', 0)), 'fallback_count')

if retarget_ratio < args.min_retarget_ratio or fallback_count > args.max_fallbacks:
    print('A116 retargeting fidelity gate failed', file=sys.stderr)
    raise SystemExit(2)
