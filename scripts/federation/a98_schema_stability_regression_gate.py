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
        print(f"A98 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def _to_float(value: object, label: str) -> float:
    try:
        return float(str(value))
    except Exception:
        print(f"A98 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument("--schema", required=True)
parser.add_argument("--max-stability-regressions", type=int, default=0)
parser.add_argument("--max-contract-violations", type=int, default=0)
parser.add_argument("--min-stability-score", type=float, default=1.0)
args = parser.parse_args()

data = _load(pathlib.Path(args.schema))

if isinstance(data, dict):
    stability_regressions = _to_int(
        data.get("stability_regressions", data.get("schema_regressions", 0)),
        "stability_regressions",
    )
    contract_violations = _to_int(
        data.get("contract_violations", data.get("schema_contract_violations", 0)),
        "contract_violations",
    )
    stability_score = _to_float(
        data.get(
            "stability_score",
            data.get("schema_stability_score", data.get("score", 1.0)),
        ),
        "stability_score",
    )
elif isinstance(data, list):
    stability_regressions = 0
    contract_violations = 0
    scores = []
    for row in data:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status", "")).strip().lower()
        if status not in {"pass", "ok", "passed", "success"}:
            stability_regressions += _to_int(
                row.get("regression_count", row.get("regressions", 0)),
                "regression_count",
            )
            contract_violations += _to_int(
                row.get("violations", row.get("contract_violation", 0)),
                "contract_violation",
            )
        if row.get("stability_score") is not None:
            scores.append(_to_float(row.get("stability_score"), "stability_score"))
        elif row.get("score") is not None:
            scores.append(_to_float(row.get("score"), "score"))
    stability_score = min(scores) if scores else 1.0
else:
    print("A98 schema stability payload must be a JSON object or CSV rows", file=sys.stderr)
    raise SystemExit(2)

if (
    stability_regressions > args.max_stability_regressions
    or contract_violations > args.max_contract_violations
    or stability_score < args.min_stability_score
):
    print("A98 schema stability regression gate failed", file=sys.stderr)
    raise SystemExit(2)
