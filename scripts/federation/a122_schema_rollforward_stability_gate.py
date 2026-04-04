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
        print(f"E122 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"E122 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--rollforward-report', required=True)
parser.add_argument('--max-rollforward-seconds', type=float, default=180.0)
parser.add_argument('--min-stability-rate', type=float, default=0.97)
parser.add_argument('--max-rollforward-breach-count', type=int, default=0)
args = parser.parse_args()

payload = load_report(pathlib.Path(args.rollforward_report))
rows = extract_rows(payload, 'schema_rollforward')

rollforward_seconds = 0.0
stability_rate = 1.0
rollforward_breach_count = 0

for row in rows:
    rollforward_seconds = max(
        rollforward_seconds,
        parse_float(
            row.get('rollforward_seconds', row.get('schema_rollforward_seconds', 0.0)),
            'rollforward_seconds',
        ),
    )
    stability_rate = min(
        stability_rate,
        parse_float(row.get('stability_rate', row.get('rollforward_stability_rate', 1.0)), 'stability_rate'),
    )
    rollforward_breach_count += parse_int(
        row.get('rollforward_breach_count', row.get('breach_count', 0)), 'rollforward_breach_count'
    )

if (
    rollforward_seconds > args.max_rollforward_seconds
    or stability_rate < args.min_stability_rate
    or rollforward_breach_count > args.max_rollforward_breach_count
):
    print('E122 schema rollforward stability gate failed', file=sys.stderr)
    raise SystemExit(2)

raise SystemExit(0)
