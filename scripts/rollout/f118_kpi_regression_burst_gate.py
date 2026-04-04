#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E118 kpi regression burst gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_int(value: object, field: str, index: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"invalid int in {field} at index {index}: {value!r}")


def to_float(value: object, field: str, index: int) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid float in {field} at index {index}: {value!r}")


def load_records(path: pathlib.Path) -> list[dict[str, object]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        except Exception:
            fail("invalid kpi csv")
        if not rows:
            fail("kpi csv must contain at least one row")
        return [dict(row) for row in rows]

    try:
        payload = json.loads(path.read_text())
    except Exception:
        fail("invalid kpi json")

    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and payload and all(isinstance(item, dict) for item in payload):
        return list(payload)
    fail("kpi payload must be a JSON object or non-empty list of objects")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kpi", required=True)
    parser.add_argument("--regression-count-field", default="regression_count")
    parser.add_argument("--max-regression-count", type=int, default=0)
    parser.add_argument("--burst-rate-field", default="regression_burst_rate")
    parser.add_argument("--max-burst-rate", type=float, default=1.0)
    args = parser.parse_args()

    records = load_records(pathlib.Path(args.kpi))
    for index, record in enumerate(records):
        regression_count = to_int(record.get(args.regression_count_field), args.regression_count_field, index)
        if regression_count > args.max_regression_count:
            fail(
                f"{args.regression_count_field}={regression_count} > "
                f"{args.max_regression_count} at index {index}"
            )

        burst_rate = to_float(record.get(args.burst_rate_field), args.burst_rate_field, index)
        if burst_rate > args.max_burst_rate:
            fail(f"{args.burst_rate_field}={burst_rate} > {args.max_burst_rate} at index {index}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
