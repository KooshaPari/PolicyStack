#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _load(path: pathlib.Path):
    raw = path.read_text()
    if path.suffix.lower() == ".csv":
        return list(csv.DictReader(raw.splitlines()))
    return json.loads(raw)


def _to_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        print(f"A95 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def _to_float(value: object, label: str) -> float:
    try:
        return float(str(value))
    except Exception:
        print(f"A95 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)

parser = argparse.ArgumentParser()
parser.add_argument("--revocations", required=True)
parser.add_argument("--max-consistency-gaps", type=int, default=0)
parser.add_argument("--max-replay-failures", type=int, default=0)
parser.add_argument("--max-budget-variance", type=float, default=0.0)
args = parser.parse_args()

data = _load(pathlib.Path(args.revocations))

if not isinstance(data, dict):
    print("A95 revocation consistency budget gate requires dict payload", file=sys.stderr)
    raise SystemExit(2)

consistency_gaps = _to_int(data.get("consistency_gaps", data.get("gaps", 0)), "consistency_gaps")
replay_failures = _to_int(data.get("replay_failures", data.get("failures", 0)), "replay_failures")
budget_variance = _to_float(
    data.get("budget_variance", data.get("variance", 0.0)),
    "budget_variance",
)

if (
    consistency_gaps > args.max_consistency_gaps
    or replay_failures > args.max_replay_failures
    or budget_variance > args.max_budget_variance
):
    print("A95 revocation consistency budget gate failed", file=sys.stderr)
    raise SystemExit(2)
