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
        print(f"E135 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"E135 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--revocation-recovery-budget-report', required=True)
parser.add_argument('--max-recovery-budget-seconds', type=float, default=120.0)
parser.add_argument('--min-recovery-budget-success-rate', type=float, default=0.97)
parser.add_argument('--max-recovery-budget-breach-count', type=int, default=0)
args = parser.parse_args()

payload = load_report(pathlib.Path(args.revocation_recovery_budget_report))
rows = extract_rows(payload, 'revocation_recovery_budget')

max_recovery_budget_seconds = 0.0
recovery_budget_success_rate = 1.0
recovery_budget_breach_count = 0

for row in rows:
    max_recovery_budget_seconds = max(
        max_recovery_budget_seconds,
        parse_float(
            row.get(
                'recovery_budget_seconds',
                row.get('revocation_recovery_budget_seconds', row.get('budget_seconds', 0.0)),
            ),
            'recovery_budget_seconds',
        ),
    )
    recovery_budget_success_rate = min(
        recovery_budget_success_rate,
        parse_float(
            row.get(
                'recovery_budget_success_rate',
                row.get('revocation_recovery_budget_success_rate', row.get('budget_success_rate', 1.0)),
            ),
            'recovery_budget_success_rate',
        ),
    )
    recovery_budget_breach_count += parse_int(
        row.get('recovery_budget_breach_count', row.get('budget_breach_count', 0)),
        'recovery_budget_breach_count',
    )

if (
    max_recovery_budget_seconds > args.max_recovery_budget_seconds
    or recovery_budget_success_rate < args.min_recovery_budget_success_rate
    or recovery_budget_breach_count > args.max_recovery_budget_breach_count
):
    print('E135 revocation recovery budget gate failed', file=sys.stderr)
    raise SystemExit(2)

raise SystemExit(0)
