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


def extract_rows(payload: list[dict[str, Any]] | dict[str, Any], lane_key: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    rows = payload.get('items') or payload.get('records') or payload.get('entries') or payload.get(lane_key)
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def parse_float(value: object, label: str) -> float:
    try:
        return float(str(value))
    except Exception:
        print(f"E125 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"E125 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--consistency-report', required=True)
parser.add_argument('--max-drift-ratio', type=float, default=0.02)
parser.add_argument('--min-consistency-rate', type=float, default=0.98)
parser.add_argument('--max-drift-breach-count', type=int, default=0)
args = parser.parse_args()

payload = load_report(pathlib.Path(args.consistency_report))
rows = extract_rows(payload, 'federation_consistency_drift')

max_drift_ratio = 0.0
consistency_rate = 1.0
drift_breach_count = 0

for row in rows:
    max_drift_ratio = max(
        max_drift_ratio,
        parse_float(row.get('drift_ratio', row.get('consistency_drift_ratio', 0.0)), 'drift_ratio'),
    )
    consistency_rate = min(
        consistency_rate,
        parse_float(
            row.get('consistency_rate', row.get('federation_consistency_rate', 1.0)),
            'consistency_rate',
        ),
    )
    drift_breach_count += parse_int(
        row.get('drift_breach_count', row.get('breach_count', 0)), 'drift_breach_count'
    )

if (
    max_drift_ratio > args.max_drift_ratio
    or consistency_rate < args.min_consistency_rate
    or drift_breach_count > args.max_drift_breach_count
):
    print('E125 federation consistency drift gate failed', file=sys.stderr)
    raise SystemExit(2)

raise SystemExit(0)
