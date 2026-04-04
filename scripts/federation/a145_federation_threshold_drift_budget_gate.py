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
        print(f"E145 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"E145 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--threshold-drift-budget-report', required=True)
parser.add_argument('--max-threshold-drift', type=float, default=0.05)
parser.add_argument('--min-threshold-drift-pass-rate', type=float, default=0.98)
parser.add_argument('--max-threshold-drift-breach-count', type=int, default=0)
args = parser.parse_args()

payload = load_report(pathlib.Path(args.threshold_drift_budget_report))
rows = extract_rows(payload, 'federation_threshold_drift_budget')

max_threshold_drift = 0.0
threshold_drift_pass_rate = 1.0
threshold_drift_breach_count = 0

for row in rows:
    max_threshold_drift = max(
        max_threshold_drift,
        parse_float(
            row.get(
                'threshold_drift',
                row.get('federation_threshold_drift', row.get('drift', 0.0)),
            ),
            'threshold_drift',
        ),
    )
    threshold_drift_pass_rate = min(
        threshold_drift_pass_rate,
        parse_float(
            row.get(
                'threshold_drift_pass_rate',
                row.get('federation_threshold_drift_pass_rate', row.get('pass_rate', 1.0)),
            ),
            'threshold_drift_pass_rate',
        ),
    )
    threshold_drift_breach_count += parse_int(
        row.get('threshold_drift_breach_count', row.get('threshold_drift_violation_count', 0)),
        'threshold_drift_breach_count',
    )

if (
    max_threshold_drift > args.max_threshold_drift
    or threshold_drift_pass_rate < args.min_threshold_drift_pass_rate
    or threshold_drift_breach_count > args.max_threshold_drift_breach_count
):
    print('E145 federation threshold drift budget gate failed', file=sys.stderr)
    raise SystemExit(2)

raise SystemExit(0)
