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
        print(f"A100 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def _to_float(value: object, label: str) -> float:
    try:
        return float(str(value))
    except Exception:
        print(f"A100 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument("--evidence", required=True)
parser.add_argument("--min-consistency-ratio", type=float, default=0.99)
parser.add_argument("--max-inconsistent-records", type=int, default=0)
parser.add_argument("--max-missing-records", type=int, default=0)
args = parser.parse_args()

data = _load(pathlib.Path(args.evidence))

if isinstance(data, dict):
    consistency_ratio = _to_float(
        data.get(
            "consistency_ratio",
            data.get("evidence_consistency_ratio", data.get("ratio", 1.0)),
        ),
        "consistency_ratio",
    )
    inconsistent_records = _to_int(
        data.get("inconsistent_records", data.get("inconsistent_count", 0)),
        "inconsistent_records",
    )
    missing_records = _to_int(
        data.get("missing_records", data.get("missing_count", 0)),
        "missing_records",
    )
elif isinstance(data, list):
    inconsistent_records = 0
    missing_records = 0
    ratios = []
    for row in data:
        if not isinstance(row, dict):
            continue
        is_consistent = str(row.get("consistent", row.get("is_consistent", "true"))).strip().lower()
        if is_consistent not in {"1", "true", "yes", "ok", "pass", "passed"}:
            inconsistent_records += 1
        missing_records += _to_int(row.get("missing", row.get("missing_count", 0)), "missing")
        if row.get("consistency_ratio") is not None:
            ratios.append(_to_float(row.get("consistency_ratio"), "consistency_ratio"))
        elif row.get("ratio") is not None:
            ratios.append(_to_float(row.get("ratio"), "ratio"))
    consistency_ratio = min(ratios) if ratios else 1.0
else:
    print("A100 chaos evidence payload must be a JSON object or CSV rows", file=sys.stderr)
    raise SystemExit(2)

if (
    consistency_ratio < args.min_consistency_ratio
    or inconsistent_records > args.max_inconsistent_records
    or missing_records > args.max_missing_records
):
    print("A100 chaos evidence consistency gate failed", file=sys.stderr)
    raise SystemExit(2)
