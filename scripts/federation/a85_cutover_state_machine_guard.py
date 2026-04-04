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


p = argparse.ArgumentParser()
p.add_argument("--state", required=True)
p.add_argument("--max-invalid-transitions", type=int, default=0)
p.add_argument("--allowed-states", default="pending,cutover,completed,rollback,failed")
args = p.parse_args()

data = load(args.state)
state = str(data.get("state", data.get("current_state", ""))).lower()
invalid = to_int(data.get("invalid_transitions", data.get("invalid_transition_count", 0)))
allowed = {s.strip().lower() for s in args.allowed_states.split(",") if s.strip()}

if state not in allowed or invalid > args.max_invalid_transitions:
    print("A85 cutover state machine guard failed", file=sys.stderr)
    raise SystemExit(2)

