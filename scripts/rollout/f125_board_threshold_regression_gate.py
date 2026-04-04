#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E125 board threshold regression gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--threshold-regression-field", default="threshold_regression")
    parser.add_argument("--max-threshold-regression", type=float, default=0.0)
    parser.add_argument(
        "--threshold-regression-violations-field", default="threshold_regression_violation_count"
    )
    parser.add_argument("--max-threshold-regression-violations", type=int, default=0)
    args = parser.parse_args()

    records = load_records(pathlib.Path(args.board))
    for index, record in enumerate(records):
        threshold_regression = to_float(
            record.get(args.threshold_regression_field), args.threshold_regression_field, index
        )
        if threshold_regression > args.max_threshold_regression:
            fail(
                f"{args.threshold_regression_field}={threshold_regression} > "
                f"{args.max_threshold_regression} at index {index}"
            )

        threshold_regression_violations = to_int(
            record.get(args.threshold_regression_violations_field),
            args.threshold_regression_violations_field,
            index,
        )
        if threshold_regression_violations > args.max_threshold_regression_violations:
            fail(
                f"{args.threshold_regression_violations_field}={threshold_regression_violations} > "
                f"{args.max_threshold_regression_violations} at index {index}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
