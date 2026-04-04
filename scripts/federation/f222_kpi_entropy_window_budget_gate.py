#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E222 kpi window regression gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--window-regression-count-field", default="window_regression_count")
    parser.add_argument("--max-window-regression-count", type=int, default=0)
    parser.add_argument("--window-days-field", default="window_days")
    parser.add_argument("--max-window-days", type=int, default=30)
    args = parser.parse_args()

    records = load_records(pathlib.Path(args.kpi))
    for index, record in enumerate(records):
        window_regressions = to_int(
            record.get(args.window_regression_count_field),
            args.window_regression_count_field,
            index,
        )
        if window_regressions > args.max_window_regression_count:
            fail(
                f"{args.window_regression_count_field}="
                f"{window_regressions} > "
                f"{args.max_window_regression_count} at index {index}"
            )

        window_days = to_int(
            record.get(args.window_days_field), args.window_days_field, index
        )
        if window_days > args.max_window_days:
            fail(f"{args.window_days_field}={window_days} > {args.max_window_days} at index {index}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
