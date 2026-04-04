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
        print(f"A115 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"A115 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--handoff-report', required=True)
parser.add_argument('--min-handoff-ratio', type=float, default=0.98)
parser.add_argument('--max-misroute-count', type=int, default=0)
args = parser.parse_args()

rows = load_report(pathlib.Path(args.handoff_report))
if isinstance(rows, dict):
    handoff_ratio = parse_float(rows.get('handoff_ratio', rows.get('handoff_accuracy', 1.0)), 'handoff_ratio')
    misroute_count = parse_int(rows.get('misroute_count', rows.get('handoff_misroutes', 0)), 'misroute_count')
else:
    handoff_ratio = 1.0
    misroute_count = 0
    for row in rows:
        if row is None:
            continue
        handoff_ratio = min(handoff_ratio, parse_float(row.get('handoff_ratio', row.get('handoff_accuracy', 1.0)), 'handoff_ratio'))
        misroute_count += parse_int(row.get('misroute_count', row.get('handoff_misroutes', 0)), 'misroute_count')

if handoff_ratio < args.min_handoff_ratio or misroute_count > args.max_misroute_count:
    print('A115 handoff consistency gate failed', file=sys.stderr)
    raise SystemExit(2)
