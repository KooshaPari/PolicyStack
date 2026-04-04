#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _fail(message: str) -> None:
    print(f"F93 kpi reliability gap gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _to_int(value: object, field: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        _fail(f"invalid integer {field}: {value!r}")


def _to_float(value: object, field: str) -> float:
    try:
        return float(str(value))
    except Exception:
        _fail(f"invalid float {field}: {value!r}")

parser = argparse.ArgumentParser()
parser.add_argument("--kpi", required=True)
parser.add_argument("--reliability-csv", required=True)
parser.add_argument("--max-gap-segments", type=int, default=0)
parser.add_argument("--max-gap-severity", type=float, default=0.0)
parser.add_argument("--max-unreliable-ratio", type=float, default=0.0)
args = parser.parse_args()

kpi = json.loads(pathlib.Path(args.kpi).read_text())
if not isinstance(kpi, dict):
    _fail("kpi must be JSON object")

rows = list(csv.DictReader(pathlib.Path(args.reliability_csv).read_text().splitlines()))
if not rows:
    _fail("empty reliability csv")

gaps = _to_int(kpi.get("gap_segments", 0), "gap_segments")
severity = _to_float(kpi.get("max_gap_severity", kpi.get("gap_severity", 0.0)), "max_gap_severity")
ratios = [_to_float(r.get("unreliable_ratio", r.get("ratio", 0.0)), "unreliable_ratio") for r in rows]
max_ratio = max(ratios) if ratios else 0.0

if gaps > args.max_gap_segments:
    _fail(f"gap_segments={gaps}")
if severity > args.max_gap_severity:
    _fail(f"max_gap_severity={severity}")
if max_ratio > args.max_unreliable_ratio:
    _fail(f"max_unreliable_ratio={max_ratio}")
