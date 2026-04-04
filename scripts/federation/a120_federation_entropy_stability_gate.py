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
        print(f"E120 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"E120 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--entropy-report', required=True)
parser.add_argument('--max-entropy-spread', type=float, default=0.20)
parser.add_argument('--min-stability-rate', type=float, default=0.95)
parser.add_argument('--max-entropy-breach-count', type=int, default=0)
args = parser.parse_args()

payload = load_report(pathlib.Path(args.entropy_report))
rows = extract_rows(payload, 'federation_entropy')

max_entropy = 0.0
min_entropy = 1.0
stability_rate = 1.0
entropy_breach_count = 0

for row in rows:
    entropy_value = parse_float(row.get('entropy', row.get('entropy_value', 0.0)), 'entropy')
    max_entropy = max(max_entropy, entropy_value)
    min_entropy = min(min_entropy, entropy_value)
    stability_rate = min(
        stability_rate,
        parse_float(row.get('stability_rate', row.get('entropy_stability_rate', 1.0)), 'stability_rate'),
    )
    entropy_breach_count += parse_int(
        row.get('entropy_breach_count', row.get('breach_count', 0)), 'entropy_breach_count'
    )

entropy_spread = max_entropy - min_entropy
if (
    entropy_spread > args.max_entropy_spread
    or stability_rate < args.min_stability_rate
    or entropy_breach_count > args.max_entropy_breach_count
):
    print('E120 federation entropy stability gate failed', file=sys.stderr)
    raise SystemExit(2)

raise SystemExit(0)
