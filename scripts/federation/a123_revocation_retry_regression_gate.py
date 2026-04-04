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
        print(f"E123 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"E123 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--retry-report', required=True)
parser.add_argument('--max-retry-latency-seconds', type=float, default=45.0)
parser.add_argument('--min-retry-success-rate', type=float, default=0.97)
parser.add_argument('--max-retry-regression-count', type=int, default=0)
args = parser.parse_args()

payload = load_report(pathlib.Path(args.retry_report))
rows = extract_rows(payload, 'revocation_retry')

retry_latency_seconds = 0.0
retry_success_rate = 1.0
retry_regression_count = 0

for row in rows:
    retry_latency_seconds = max(
        retry_latency_seconds,
        parse_float(
            row.get('retry_latency_seconds', row.get('revocation_retry_latency_seconds', 0.0)),
            'retry_latency_seconds',
        ),
    )
    retry_success_rate = min(
        retry_success_rate,
        parse_float(
            row.get('retry_success_rate', row.get('revocation_retry_success_rate', 1.0)),
            'retry_success_rate',
        ),
    )
    retry_regression_count += parse_int(
        row.get('retry_regression_count', row.get('regression_count', 0)), 'retry_regression_count'
    )

if (
    retry_latency_seconds > args.max_retry_latency_seconds
    or retry_success_rate < args.min_retry_success_rate
    or retry_regression_count > args.max_retry_regression_count
):
    print('E123 revocation retry regression gate failed', file=sys.stderr)
    raise SystemExit(2)

raise SystemExit(0)
