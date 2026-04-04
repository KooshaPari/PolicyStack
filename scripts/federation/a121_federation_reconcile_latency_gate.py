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
        print(f"E121 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"E121 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--reconcile-report', required=True)
parser.add_argument('--max-reconcile-latency-seconds', type=float, default=75.0)
parser.add_argument('--min-reconcile-success-rate', type=float, default=0.98)
parser.add_argument('--max-latency-breach-count', type=int, default=0)
args = parser.parse_args()

payload = load_report(pathlib.Path(args.reconcile_report))
rows = extract_rows(payload, 'federation_reconcile')

reconcile_latency_seconds = 0.0
reconcile_success_rate = 1.0
latency_breach_count = 0

for row in rows:
    reconcile_latency_seconds = max(
        reconcile_latency_seconds,
        parse_float(
            row.get('reconcile_latency_seconds', row.get('federation_reconcile_latency_seconds', 0.0)),
            'reconcile_latency_seconds',
        ),
    )
    reconcile_success_rate = min(
        reconcile_success_rate,
        parse_float(
            row.get('reconcile_success_rate', row.get('federation_reconcile_success_rate', 1.0)),
            'reconcile_success_rate',
        ),
    )
    latency_breach_count += parse_int(
        row.get('latency_breach_count', row.get('breach_count', 0)), 'latency_breach_count'
    )

if (
    reconcile_latency_seconds > args.max_reconcile_latency_seconds
    or reconcile_success_rate < args.min_reconcile_success_rate
    or latency_breach_count > args.max_latency_breach_count
):
    print('E121 federation reconcile latency gate failed', file=sys.stderr)
    raise SystemExit(2)

raise SystemExit(0)
