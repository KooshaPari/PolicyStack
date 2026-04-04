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
        print(f"A94 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def _to_ratio(value: object, label: str) -> float:
    try:
        return float(str(value))
    except Exception:
        print(f"A94 invalid ratio for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)

parser = argparse.ArgumentParser()
parser.add_argument("--drift", required=True)
parser.add_argument("--max-drift-count", type=int, default=0)
parser.add_argument("--max-missing-required", type=int, default=0)
parser.add_argument("--min-schema-match", type=float, default=1.0)
args = parser.parse_args()

data = _load(pathlib.Path(args.drift))

if isinstance(data, dict):
    drift_count = _to_int(data.get("drift_count", data.get("schema_drift_count", 0)), "drift_count")
    missing_required = _to_int(data.get("missing_required", data.get("required_missing", 0)), "missing_required")
    match_ratio = _to_ratio(
        data.get("schema_match_ratio", data.get("drift_ratio", data.get("schema_match", 0.0))),
        "schema_match_ratio",
    )
elif isinstance(data, list):
    drift_count = 0
    missing_required = 0
    matches = []
    for row in data:
        if not isinstance(row, dict):
            continue
        if _to_int(row.get("is_drift", row.get("drift", 0)), "is_drift") > 0:
            drift_count += 1
        if _to_int(row.get("required_missing", row.get("missing", 0)), "required_missing") > 0:
            missing_required += 1
        m = row.get("match_ratio")
        if m is not None:
            matches.append(_to_ratio(m, "match_ratio"))
    match_ratio = sum(matches) / len(matches) if matches else 1.0
else:
    print("A94 invalid drift payload", file=sys.stderr)
    raise SystemExit(2)

if (
    drift_count > args.max_drift_count
    or missing_required > args.max_missing_required
    or match_ratio < args.min_schema_match
):
    print("A94 cutover schema drift gate failed", file=sys.stderr)
    raise SystemExit(2)
