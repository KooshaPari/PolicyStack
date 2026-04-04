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


p = argparse.ArgumentParser()
p.add_argument("--compat", required=True)
p.add_argument("--min-compat-score", type=float, default=1.0)
p.add_argument("--max-missing-fields", type=int, default=0)
args = p.parse_args()

c = load(args.compat)
score = to_float(c.get("rollback_compat_score", c.get("compatibility_score", 0.0)))
missing = to_int(c.get("missing_fields", c.get("missing_rollback_fields", 0)))
compatible = bool(c.get("rollback_compatible", c.get("schema_rollback_compatible", True)))

if not compatible or missing > args.max_missing_fields or score < args.min_compat_score:
    print("A86 schema rollback compat gate failed", file=sys.stderr)
    raise SystemExit(2)

