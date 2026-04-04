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
        print(f"E119 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"E119 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--revocation-report', required=True)
parser.add_argument('--max-recovery-seconds', type=float, default=90.0)
parser.add_argument('--min-recovery-rate', type=float, default=0.97)
parser.add_argument('--max-regression-count', type=int, default=0)
args = parser.parse_args()

payload = load_report(pathlib.Path(args.revocation_report))
rows = extract_rows(payload, 'revocation_recovery')

recovery_seconds = 0.0
recovery_rate = 1.0
regression_count = 0

for row in rows:
    recovery_seconds = max(
        recovery_seconds,
        parse_float(row.get('recovery_seconds', row.get('revocation_recovery_seconds', 0.0)), 'recovery_seconds'),
    )
    recovery_rate = min(
        recovery_rate,
        parse_float(row.get('recovery_rate', row.get('revocation_recovery_rate', 1.0)), 'recovery_rate'),
    )
    regression_count += parse_int(
        row.get('regression_count', row.get('recovery_regressions', 0)), 'regression_count'
    )

if (
    recovery_seconds > args.max_recovery_seconds
    or recovery_rate < args.min_recovery_rate
    or regression_count > args.max_regression_count
):
    print('E119 revocation recovery regression gate failed', file=sys.stderr)
    raise SystemExit(2)

raise SystemExit(0)
