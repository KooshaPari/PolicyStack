#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E121 board threshold drift gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(value: object, field: str, index: int) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid float in {field} at index {index}: {value!r}")


def to_int(value: object, field: str, index: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"invalid int in {field} at index {index}: {value!r}")


def load_records(path: pathlib.Path) -> list[dict[str, object]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        except Exception:
            fail("invalid board csv")
        if not rows:
            fail("board csv must contain at least one row")
        return [dict(row) for row in rows]

    try:
        payload = json.loads(path.read_text())
    except Exception:
        fail("invalid board json")

    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and payload and all(isinstance(item, dict) for item in payload):
        return list(payload)
    fail("board payload must be a JSON object or non-empty list of objects")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", required=True)
    parser.add_argument("--threshold-drift-field", default="threshold_drift")
    parser.add_argument("--max-threshold-drift", type=float, default=0.05)
    parser.add_argument("--drift-violations-field", default="threshold_drift_violation_count")
    parser.add_argument("--max-drift-violations", type=int, default=0)
    args = parser.parse_args()

    records = load_records(pathlib.Path(args.board))
    for index, record in enumerate(records):
        threshold_drift = to_float(record.get(args.threshold_drift_field), args.threshold_drift_field, index)
        if threshold_drift > args.max_threshold_drift:
            fail(
                f"{args.threshold_drift_field}={threshold_drift} > "
                f"{args.max_threshold_drift} at index {index}"
            )

        drift_violations = to_int(record.get(args.drift_violations_field), args.drift_violations_field, index)
        if drift_violations > args.max_drift_violations:
            fail(
                f"{args.drift_violations_field}={drift_violations} > "
                f"{args.max_drift_violations} at index {index}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
