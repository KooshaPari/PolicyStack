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


def parse_float(value: object, label: str) -> float:
    try:
        return float(str(value))
    except Exception:
        print(f"A114 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"A114 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--watchdog-report', required=True)
parser.add_argument('--max-stall-seconds', type=float, default=30.0)
parser.add_argument('--max-timeout-count', type=int, default=0)
args = parser.parse_args()

rows = load_report(pathlib.Path(args.watchdog_report))
if isinstance(rows, dict):
    max_stall_seconds = parse_float(rows.get('max_stall_seconds', rows.get('stall_seconds', 0.0)), 'max_stall_seconds')
    timeout_count = parse_int(rows.get('timeout_count', rows.get('timeouts', 0)), 'timeout_count')
else:
    max_stall_seconds = 0.0
    timeout_count = 0
    for row in rows:
        if row is None:
            continue
        max_stall_seconds = max(max_stall_seconds, parse_float(row.get('max_stall_seconds', row.get('stall_seconds', 0.0)), 'max_stall_seconds'))
        timeout_count += parse_int(row.get('timeout_count', row.get('timeouts', 0)), 'timeout_count')

if max_stall_seconds > args.max_stall_seconds or timeout_count > args.max_timeout_count:
    print('A114 watchdog budget gate failed', file=sys.stderr)
    raise SystemExit(2)
