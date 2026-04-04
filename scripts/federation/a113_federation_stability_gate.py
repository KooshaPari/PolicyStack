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


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"A113 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def parse_float(value: object, label: str) -> float:
    try:
        return float(str(value))
    except Exception:
        print(f"A113 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument('--stability-report', required=True)
parser.add_argument('--min-stability-score', type=float, default=0.97)
parser.add_argument('--max-incident-bursts', type=int, default=0)
args = parser.parse_args()

rows = load_report(pathlib.Path(args.stability_report))
if isinstance(rows, dict):
    stability = parse_float(rows.get('stability_score', rows.get('score', 1.0)), 'stability_score')
    incident_bursts = parse_int(rows.get('incident_bursts', rows.get('burst_count', 0)), 'incident_bursts')
else:
    stability = 1.0
    incident_bursts = 0
    for row in rows:
        if row is None:
            continue
        stability = min(stability, parse_float(row.get('stability_score', row.get('score', 1.0)), 'stability_score'))
        incident_bursts = max(incident_bursts, parse_int(row.get('incident_bursts', row.get('burst_count', 0)), 'incident_bursts'))

if stability < args.min_stability_score or incident_bursts > args.max_incident_bursts:
    print('A113 federation stability gate failed', file=sys.stderr)
    raise SystemExit(2)
