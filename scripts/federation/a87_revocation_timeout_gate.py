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


def to_float(v):
    return float(v) if str(v).strip() else 0.0


p = argparse.ArgumentParser()
p.add_argument("--timings", required=True)
p.add_argument("--max-timeout-ms", type=float, default=500.0)
p.add_argument("--max-failures", type=int, default=0)
args = p.parse_args()

t = load(args.timings)
timeout = to_float(
    t.get("revocation_timeout_ms", t.get("max_revocation_timeout_ms", t.get("max_timeout_ms", 0)))
)
failures = int(to_float(t.get("timeout_failures", t.get("revocation_timeout_failures", 0))))

if timeout > args.max_timeout_ms or failures > args.max_failures:
    print("A87 revocation timeout gate failed", file=sys.stderr)
    raise SystemExit(2)

