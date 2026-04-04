#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _fail(message: str) -> None:
    print(f"F95 succession risk distribution gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _to_int(value: object, field: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        _fail(f"invalid integer {field}: {value!r}")

parser = argparse.ArgumentParser()
parser.add_argument("--distribution", required=True)
parser.add_argument("--succesion-csv", required=True)
parser.add_argument("--max-high-risk", type=int, default=0)
parser.add_argument("--max-risk-skew", type=float, default=0.0)
parser.add_argument("--max-missing-coverage", type=float, default=1.0)
args = parser.parse_args()

report = json.loads(pathlib.Path(args.distribution).read_text())
rows = list(csv.DictReader(pathlib.Path(args.succesion_csv).read_text().splitlines()))

if not isinstance(report, dict):
    _fail("distribution must be JSON object")

high_risk = _to_int(report.get("high_risk_count", report.get("high_risk", 0)), "high_risk_count")
if high_risk > args.max_high_risk:
    _fail(f"high_risk_count={high_risk}")

risk_total = _to_int(report.get("total_records", report.get("risk_total", len(rows))), "total_records")
covered = sum(1 for row in rows if str(row.get("risk_bucket", "")).strip())
coverage = covered / max(1, len(rows))
if coverage < args.max_missing_coverage:
    _fail(f"coverage={coverage}")

skew = float(report.get("risk_skew", 0.0) or 0.0)
if skew > args.max_risk_skew:
    _fail(f"risk_skew={skew}")
