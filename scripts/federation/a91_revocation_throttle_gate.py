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
parser.add_argument("--revocation", required=True)
parser.add_argument("--max-throttle-events", type=int, default=0)
parser.add_argument("--max-throttle-ops", type=int, default=0)
parser.add_argument("--max-throttle-delay-ms", type=float, default=0.0)
args = parser.parse_args()

data = load(args.revocation)
throttle_events = to_int(
    data.get("throttle_events", data.get("revocation_throttle_events", data.get("throttle_count", 0)))
)
throttle_ops = to_int(
    data.get("throttle_ops", data.get("revocation_throttle_ops", data.get("ops_delayed", 0)))
)
delay_ms = to_float(
    data.get("max_throttle_delay_ms", data.get("throttle_delay_ms", data.get("delay_ms", 0.0)))
)

if (
    throttle_events > args.max_throttle_events
    or throttle_ops > args.max_throttle_ops
    or delay_ms > args.max_throttle_delay_ms
):
    print("A91 revocation throttle gate failed", file=sys.stderr)
    raise SystemExit(2)
