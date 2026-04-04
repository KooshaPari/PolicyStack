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
        print(f"E140 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"E140 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--entropy-budget-window-report', required=True)
parser.add_argument('--max-entropy-budget-window-seconds', type=float, default=300.0)
parser.add_argument('--min-entropy-budget-window-pass-rate', type=float, default=0.95)
parser.add_argument('--max-entropy-budget-window-breach-count', type=int, default=0)
args = parser.parse_args()

payload = load_report(pathlib.Path(args.entropy_budget_window_report))
rows = extract_rows(payload, 'federation_entropy_budget_window')

max_entropy_budget_window_seconds = 0.0
entropy_budget_window_pass_rate = 1.0
entropy_budget_window_breach_count = 0

for row in rows:
    max_entropy_budget_window_seconds = max(
        max_entropy_budget_window_seconds,
        parse_float(
            row.get(
                'entropy_budget_window_seconds',
                row.get('federation_entropy_budget_window_seconds', row.get('window_seconds', 0.0)),
            ),
            'entropy_budget_window_seconds',
        ),
    )
    entropy_budget_window_pass_rate = min(
        entropy_budget_window_pass_rate,
        parse_float(
            row.get(
                'entropy_budget_window_pass_rate',
                row.get('federation_entropy_budget_window_pass_rate', row.get('window_pass_rate', 1.0)),
            ),
            'entropy_budget_window_pass_rate',
        ),
    )
    entropy_budget_window_breach_count += parse_int(
        row.get('entropy_budget_window_breach_count', row.get('window_breach_count', 0)),
        'entropy_budget_window_breach_count',
    )

if (
    max_entropy_budget_window_seconds > args.max_entropy_budget_window_seconds
    or entropy_budget_window_pass_rate < args.min_entropy_budget_window_pass_rate
    or entropy_budget_window_breach_count > args.max_entropy_budget_window_breach_count
):
    print('E140 federation entropy budget window gate failed', file=sys.stderr)
    raise SystemExit(2)

raise SystemExit(0)
