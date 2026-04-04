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
        print(f"E131 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"E131 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--revocation-recovery-report', required=True)
parser.add_argument('--max-recovery-window-seconds', type=float, default=120.0)
parser.add_argument('--min-recovery-success-rate', type=float, default=0.97)
parser.add_argument('--max-recovery-breach-count', type=int, default=0)
args = parser.parse_args()

payload = load_report(pathlib.Path(args.revocation_recovery_report))
rows = extract_rows(payload, 'revocation_recovery_window')

max_recovery_window_seconds = 0.0
recovery_success_rate = 1.0
recovery_breach_count = 0

for row in rows:
    max_recovery_window_seconds = max(
        max_recovery_window_seconds,
        parse_float(
            row.get(
                'recovery_window_seconds',
                row.get('revocation_recovery_window_seconds', row.get('window_seconds', 0.0)),
            ),
            'recovery_window_seconds',
        ),
    )
    recovery_success_rate = min(
        recovery_success_rate,
        parse_float(
            row.get(
                'recovery_success_rate',
                row.get('revocation_recovery_success_rate', row.get('window_success_rate', 1.0)),
            ),
            'recovery_success_rate',
        ),
    )
    recovery_breach_count += parse_int(
        row.get('recovery_breach_count', row.get('window_breach_count', 0)),
        'recovery_breach_count',
    )

if (
    max_recovery_window_seconds > args.max_recovery_window_seconds
    or recovery_success_rate < args.min_recovery_success_rate
    or recovery_breach_count > args.max_recovery_breach_count
):
    print('E131 revocation recovery window gate failed', file=sys.stderr)
    raise SystemExit(2)

raise SystemExit(0)
