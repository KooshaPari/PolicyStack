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
        print(f"E129 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"E129 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--consistency-window-report', required=True)
parser.add_argument('--max-window-regression-rate', type=float, default=0.02)
parser.add_argument('--min-window-consistency-rate', type=float, default=0.98)
parser.add_argument('--max-window-regression-count', type=int, default=0)
args = parser.parse_args()

payload = load_report(pathlib.Path(args.consistency_window_report))
rows = extract_rows(payload, 'federation_consistency_window_regression')

max_window_regression_rate = 0.0
window_consistency_rate = 1.0
window_regression_count = 0

for row in rows:
    max_window_regression_rate = max(
        max_window_regression_rate,
        parse_float(
            row.get(
                'window_regression_rate',
                row.get('consistency_window_regression_rate', row.get('regression_rate', 0.0)),
            ),
            'window_regression_rate',
        ),
    )
    window_consistency_rate = min(
        window_consistency_rate,
        parse_float(
            row.get(
                'window_consistency_rate',
                row.get('federation_window_consistency_rate', row.get('consistency_rate', 1.0)),
            ),
            'window_consistency_rate',
        ),
    )
    window_regression_count += parse_int(
        row.get('window_regression_count', row.get('regression_count', 0)),
        'window_regression_count',
    )

if (
    max_window_regression_rate > args.max_window_regression_rate
    or window_consistency_rate < args.min_window_consistency_rate
    or window_regression_count > args.max_window_regression_count
):
    print('E129 federation consistency window regression gate failed', file=sys.stderr)
    raise SystemExit(2)

raise SystemExit(0)
