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
parser.add_argument("--schema", required=True)
parser.add_argument("--max-missing-instrumented-fields", type=int, default=0)
parser.add_argument("--max-instrumentation-gaps", type=int, default=0)
parser.add_argument("--min-instrumentation-rate", type=float, default=1.0)
args = parser.parse_args()

data = load(args.schema)
missing = to_int(
    data.get("missing_instrumented_fields", data.get("missing_fields", data.get("missing", 0)))
)
gaps = to_int(data.get("instrumentation_gaps", data.get("schema_gaps", 0)))
rate = to_float(
    data.get("instrumentation_rate", data.get("instrumented_rate", data.get("coverage", 1.0)))
)

if (
    missing > args.max_missing_instrumented_fields
    or gaps > args.max_instrumentation_gaps
    or rate < args.min_instrumentation_rate
):
    print("A90 schema instrumentation gate failed", file=sys.stderr)
    raise SystemExit(2)
