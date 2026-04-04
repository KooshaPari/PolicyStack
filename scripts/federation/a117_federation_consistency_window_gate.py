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
        print(f"E117 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"E117 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--consistency-report', required=True)
parser.add_argument('--min-consistency-rate', type=float, default=0.98)
parser.add_argument('--max-window-seconds', type=float, default=60.0)
parser.add_argument('--max-window-breach-count', type=int, default=0)
args = parser.parse_args()

payload = load_report(pathlib.Path(args.consistency_report))
rows = extract_rows(payload, 'consistency_windows')

consistency_rate = 1.0
window_seconds = 0.0
window_breach_count = 0

for row in rows:
    consistency_rate = min(
        consistency_rate,
        parse_float(row.get('consistency_rate', row.get('rate', 1.0)), 'consistency_rate'),
    )
    window_seconds = max(
        window_seconds,
        parse_float(row.get('window_seconds', row.get('consistency_window_seconds', 0.0)), 'window_seconds'),
    )
    window_breach_count += parse_int(
        row.get('window_breach_count', row.get('breach_count', 0)), 'window_breach_count'
    )

if (
    consistency_rate < args.min_consistency_rate
    or window_seconds > args.max_window_seconds
    or window_breach_count > args.max_window_breach_count
):
    print('E117 federation consistency window gate failed', file=sys.stderr)
    raise SystemExit(2)

raise SystemExit(0)
