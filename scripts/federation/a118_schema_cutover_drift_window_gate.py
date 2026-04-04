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
        print(f"E118 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"E118 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--drift-report', required=True)
parser.add_argument('--max-schema-drift-rate', type=float, default=0.02)
parser.add_argument('--max-cutover-window-seconds', type=float, default=120.0)
parser.add_argument('--max-drift-breach-count', type=int, default=0)
args = parser.parse_args()

payload = load_report(pathlib.Path(args.drift_report))
rows = extract_rows(payload, 'schema_cutover_windows')

schema_drift_rate = 0.0
cutover_window_seconds = 0.0
drift_breach_count = 0

for row in rows:
    schema_drift_rate = max(
        schema_drift_rate,
        parse_float(row.get('schema_drift_rate', row.get('drift_rate', 0.0)), 'schema_drift_rate'),
    )
    cutover_window_seconds = max(
        cutover_window_seconds,
        parse_float(
            row.get('cutover_window_seconds', row.get('schema_cutover_window_seconds', 0.0)),
            'cutover_window_seconds',
        ),
    )
    drift_breach_count += parse_int(
        row.get('drift_breach_count', row.get('breach_count', 0)), 'drift_breach_count'
    )

if (
    schema_drift_rate > args.max_schema_drift_rate
    or cutover_window_seconds > args.max_cutover_window_seconds
    or drift_breach_count > args.max_drift_breach_count
):
    print('E118 schema cutover drift window gate failed', file=sys.stderr)
    raise SystemExit(2)

raise SystemExit(0)
