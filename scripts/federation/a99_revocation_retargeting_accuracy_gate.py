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
        print(f"A99 invalid integer for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


def _to_float(value: object, label: str) -> float:
    try:
        return float(str(value))
    except Exception:
        print(f"A99 invalid float for {label}: {value!r}", file=sys.stderr)
        raise SystemExit(2)


parser = argparse.ArgumentParser()
parser.add_argument("--revocations", required=True)
parser.add_argument("--min-accuracy", type=float, default=0.98)
parser.add_argument("--max-precision-error-rate", type=float, default=0.05)
parser.add_argument("--max-mis-targets", type=int, default=0)
args = parser.parse_args()

data = _load(pathlib.Path(args.revocations))

if isinstance(data, dict):
    accuracy = _to_float(
        data.get(
            "targeting_accuracy",
            data.get("revocation_targeting_accuracy", data.get("accuracy", 1.0)),
        ),
        "targeting_accuracy",
    )
    precision_error_rate = _to_float(
        data.get("precision_error_rate", data.get("target_error_rate", 0.0)),
        "precision_error_rate",
    )
    mis_targets = _to_int(
        data.get("mis_targets", data.get("wrong_targets", 0)),
        "mis_targets",
    )
elif isinstance(data, list):
    rows = [row for row in data if isinstance(row, dict)]
    if not rows:
        accuracy = 1.0
        precision_error_rate = 0.0
        mis_targets = 0
    else:
        correct = 0
        total = 0
        precision_rates = []
        mis_targets = 0
        for row in rows:
            total += 1
            is_correct = str(row.get("correct", row.get("is_correct", "true"))).strip().lower()
            if is_correct in {"1", "true", "yes", "ok", "pass", "passed"}:
                correct += 1
            mis_targets += _to_int(row.get("mis_target", row.get("mismatch", 0)), "mis_target")
            if row.get("precision_error_rate") is not None:
                precision_rates.append(
                    _to_float(row.get("precision_error_rate"), "precision_error_rate"),
                )
        accuracy = float(correct / total) if total else 1.0
        precision_error_rate = max(precision_rates) if precision_rates else 0.0
else:
    print("A99 revocation payload must be a JSON object or CSV rows", file=sys.stderr)
    raise SystemExit(2)

if (
    accuracy < args.min_accuracy
    or precision_error_rate > args.max_precision_error_rate
    or mis_targets > args.max_mis_targets
):
    print("A99 revocation retargeting accuracy gate failed", file=sys.stderr)
    raise SystemExit(2)
