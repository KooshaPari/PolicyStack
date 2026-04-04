#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E129 board threshold window regression gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


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
    parser.add_argument(
        "--threshold-window-regression-count-field", default="threshold_window_regression_count"
    )
    parser.add_argument("--max-threshold-window-regression-count", type=int, default=0)
    parser.add_argument("--threshold-window-days-field", default="threshold_window_days")
    parser.add_argument("--max-threshold-window-days", type=int, default=30)
    args = parser.parse_args()

    records = load_records(pathlib.Path(args.board))
    for index, record in enumerate(records):
        threshold_window_regressions = to_int(
            record.get(args.threshold_window_regression_count_field),
            args.threshold_window_regression_count_field,
            index,
        )
        if threshold_window_regressions > args.max_threshold_window_regression_count:
            fail(
                f"{args.threshold_window_regression_count_field}={threshold_window_regressions} > "
                f"{args.max_threshold_window_regression_count} at index {index}"
            )

        threshold_window_days = to_int(
            record.get(args.threshold_window_days_field), args.threshold_window_days_field, index
        )
        if threshold_window_days > args.max_threshold_window_days:
            fail(
                f"{args.threshold_window_days_field}={threshold_window_days} > "
                f"{args.max_threshold_window_days} at index {index}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
