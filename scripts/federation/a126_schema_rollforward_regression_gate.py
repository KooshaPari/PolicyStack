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
        print(f"E126 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"E126 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--rollforward-report', required=True)
parser.add_argument('--max-rollforward-regression-rate', type=float, default=0.01)
parser.add_argument('--min-rollforward-success-rate', type=float, default=0.98)
parser.add_argument('--max-regression-count', type=int, default=0)
args = parser.parse_args()

payload = load_report(pathlib.Path(args.rollforward_report))
rows = extract_rows(payload, 'schema_rollforward_regression')

max_rollforward_regression_rate = 0.0
rollforward_success_rate = 1.0
regression_count = 0

for row in rows:
    max_rollforward_regression_rate = max(
        max_rollforward_regression_rate,
        parse_float(
            row.get('rollforward_regression_rate', row.get('schema_rollforward_regression_rate', 0.0)),
            'rollforward_regression_rate',
        ),
    )
    rollforward_success_rate = min(
        rollforward_success_rate,
        parse_float(
            row.get('rollforward_success_rate', row.get('schema_rollforward_success_rate', 1.0)),
            'rollforward_success_rate',
        ),
    )
    regression_count += parse_int(row.get('regression_count', 0), 'regression_count')

if (
    max_rollforward_regression_rate > args.max_rollforward_regression_rate
    or rollforward_success_rate < args.min_rollforward_success_rate
    or regression_count > args.max_regression_count
):
    print('E126 schema rollforward regression gate failed', file=sys.stderr)
    raise SystemExit(2)

raise SystemExit(0)
