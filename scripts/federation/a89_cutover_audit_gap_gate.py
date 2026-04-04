#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def load(path):
    raw = pathlib.Path(path).read_text()
    if str(path).lower().endswith(".csv"):
        rows = list(csv.DictReader(raw.splitlines()))
        return rows[0] if rows else {}
    return json.loads(raw)


def to_int(v):
    return int(float(v)) if str(v).strip() else 0


def to_float(v):
    return float(v) if str(v).strip() else 0.0


parser = argparse.ArgumentParser()
parser.add_argument("--audit", required=True)
parser.add_argument("--max-audit-gap-events", type=int, default=0)
parser.add_argument("--max-missing-events", type=int, default=0)
parser.add_argument("--min-audit-coverage", type=float, default=1.0)
args = parser.parse_args()

data = load(args.audit)
gap_events = to_int(
    data.get("audit_gap_events", data.get("cutover_audit_gaps", data.get("gap_events", 0)))
)
missing_events = to_int(
    data.get(
        "missing_audit_events",
        data.get("missing_events", data.get("unobserved_events", 0)),
    )
)
coverage = to_float(data.get("audit_coverage", data.get("coverage", data.get("coverage_ratio", 1.0))))

if (
    gap_events > args.max_audit_gap_events
    or missing_events > args.max_missing_events
    or coverage < args.min_audit_coverage
):
    print("A89 cutover audit gap gate failed", file=sys.stderr)
    raise SystemExit(2)
