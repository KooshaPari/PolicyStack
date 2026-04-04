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
        print(f"A97 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def _to_float(value: object, label: str) -> float:
    try:
        return float(str(value))
    except Exception:
        print(f"A97 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument("--continuity", required=True)
parser.add_argument("--max-continuity-gaps", type=int, default=0)
parser.add_argument("--max-stalled-states", type=int, default=0)
parser.add_argument("--min-continuity-coverage", type=float, default=1.0)
args = parser.parse_args()

data = _load(pathlib.Path(args.continuity))

if isinstance(data, dict):
    continuity_gaps = _to_int(
        data.get("continuity_gaps", data.get("cutover_continuity_gaps", 0)),
        "continuity_gaps",
    )
    stalled_states = _to_int(
        data.get("stalled_states", data.get("stalled_continuity_states", 0)),
        "stalled_states",
    )
    continuity_coverage = _to_float(
        data.get(
            "continuity_coverage",
            data.get("coverage_ratio", data.get("coverage", 1.0)),
        ),
        "continuity_coverage",
    )
elif isinstance(data, list):
    continuity_gaps = 0
    stalled_states = 0
    coverages = []
    for row in data:
        if not isinstance(row, dict):
            continue
        continuity_gaps += _to_int(row.get("continuity_gap", 0), "continuity_gap")
        stalled_states += _to_int(
            row.get("stalled", row.get("stalled_state", 0)),
            "stalled_state",
        )
        if row.get("continuity_coverage") is not None:
            coverages.append(
                _to_float(row.get("continuity_coverage"), "continuity_coverage"),
            )
    continuity_coverage = min(coverages) if coverages else 1.0
else:
    print("A97 continuity payload must be a JSON object or CSV rows", file=sys.stderr)
    raise SystemExit(2)

if (
    continuity_gaps > args.max_continuity_gaps
    or stalled_states > args.max_stalled_states
    or continuity_coverage < args.min_continuity_coverage
):
    print("A97 cutover continuity gap gate failed", file=sys.stderr)
    raise SystemExit(2)
