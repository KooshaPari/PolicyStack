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
        print(f"A96 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def _to_float(value: object, label: str) -> float:
    try:
        return float(str(value))
    except Exception:
        print(f"A96 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)

parser = argparse.ArgumentParser()
parser.add_argument("--chaos-evidence", required=True)
parser.add_argument("--max-regressions", type=int, default=0)
parser.add_argument("--max-regression-gap", type=int, default=0)
parser.add_argument("--max-evidence-regression-rate", type=float, default=1.0)
args = parser.parse_args()

data = _load(pathlib.Path(args.chaos_evidence))

if isinstance(data, dict):
    regressions = _to_int(data.get("regressions", data.get("regression_count", 0)), "regressions")
    gap = _to_int(data.get("regression_gap", data.get("max_gap", 0)), "regression_gap")
    rate = _to_float(
        data.get("regression_rate", data.get("evidence_regression_rate", 0.0)),
        "regression_rate",
    )
elif isinstance(data, list):
    regressions = 0
    gap = 0
    rates = []
    for row in data:
        if not isinstance(row, dict):
            continue
        if _to_int(row.get("regressed", row.get("regression", 0)), "regressed") > 0:
            regressions += 1
        gap = max(gap, _to_int(row.get("gap", 0), "gap"))
        r = row.get("regression_rate")
        if r is not None:
            rates.append(_to_float(r, "regression_rate"))
    rate = sum(rates) / len(rates) if rates else 0.0
else:
    print("A96 invalid chaos evidence payload", file=sys.stderr)
    raise SystemExit(2)

if (
    regressions > args.max_regressions
    or gap > args.max_regression_gap
    or rate > args.max_evidence_regression_rate
):
    print("A96 chaos evidence regression gate failed", file=sys.stderr)
    raise SystemExit(2)
