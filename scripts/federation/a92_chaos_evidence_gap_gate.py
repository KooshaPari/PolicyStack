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
parser.add_argument("--evidence", required=True)
parser.add_argument("--max-evidence-gaps", type=int, default=0)
parser.add_argument("--max-window-gaps", type=int, default=0)
parser.add_argument("--min-window-coverage", type=float, default=1.0)
args = parser.parse_args()

data = load(args.evidence)
evidence_gaps = to_int(data.get("evidence_gaps", data.get("chaos_evidence_gaps", 0)))
window_gaps = to_int(data.get("window_gaps", data.get("gap_windows", 0)))
coverage = to_float(
    data.get(
        "window_coverage",
        data.get("coverage_ratio", data.get("evidence_coverage", 1.0)),
    )
)

if (
    evidence_gaps > args.max_evidence_gaps
    or window_gaps > args.max_window_gaps
    or coverage < args.min_window_coverage
):
    print("A92 chaos evidence gap gate failed", file=sys.stderr)
    raise SystemExit(2)
