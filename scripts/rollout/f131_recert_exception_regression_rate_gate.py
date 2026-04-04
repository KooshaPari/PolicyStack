#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E131 recert exception regression rate gate failed: {message}", file=sys.stderr)
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
            fail("invalid recert csv")
        if not rows:
            fail("recert csv must contain at least one row")
        return [dict(row) for row in rows]

    try:
        payload = json.loads(path.read_text())
    except Exception:
        fail("invalid recert json")

    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and payload and all(isinstance(item, dict) for item in payload):
        return list(payload)
    fail("recert payload must be a JSON object or non-empty list of objects")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recert", required=True)
    parser.add_argument("--exception-regression-rate-field", default="exception_regression_rate")
    parser.add_argument("--max-exception-regression-rate", type=float, default=0.0)
    parser.add_argument("--exception-regression-count-field", default="exception_regression_count")
    parser.add_argument("--max-exception-regression-count", type=int, default=0)
    args = parser.parse_args()

    records = load_records(pathlib.Path(args.recert))
    for index, record in enumerate(records):
        exception_regression_rate = to_float(
            record.get(args.exception_regression_rate_field),
            args.exception_regression_rate_field,
            index,
        )
        if exception_regression_rate > args.max_exception_regression_rate:
            fail(
                f"{args.exception_regression_rate_field}={exception_regression_rate} > "
                f"{args.max_exception_regression_rate} at index {index}"
            )

        exception_regression_count = to_int(
            record.get(args.exception_regression_count_field),
            args.exception_regression_count_field,
            index,
        )
        if exception_regression_count > args.max_exception_regression_count:
            fail(
                f"{args.exception_regression_count_field}={exception_regression_count} > "
                f"{args.max_exception_regression_count} at index {index}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
