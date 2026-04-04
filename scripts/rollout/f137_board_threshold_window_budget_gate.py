#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E137 board threshold window budget gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--threshold-window-budget-spent-field", default="threshold_window_budget_spent")
    parser.add_argument("--max-threshold-window-budget-spent", type=float, default=1.0)
    parser.add_argument(
        "--over-threshold-window-budget-count-field", default="over_threshold_window_budget_count"
    )
    parser.add_argument("--max-over-threshold-window-budget-count", type=int, default=0)
    args = parser.parse_args()

    records = load_records(pathlib.Path(args.board))
    for index, record in enumerate(records):
        threshold_window_budget_spent = to_float(
            record.get(args.threshold_window_budget_spent_field),
            args.threshold_window_budget_spent_field,
            index,
        )
        if threshold_window_budget_spent > args.max_threshold_window_budget_spent:
            fail(
                f"{args.threshold_window_budget_spent_field}={threshold_window_budget_spent} > "
                f"{args.max_threshold_window_budget_spent} at index {index}"
            )

        over_threshold_window_budget_count = to_int(
            record.get(args.over_threshold_window_budget_count_field),
            args.over_threshold_window_budget_count_field,
            index,
        )
        if over_threshold_window_budget_count > args.max_over_threshold_window_budget_count:
            fail(
                f"{args.over_threshold_window_budget_count_field}="
                f"{over_threshold_window_budget_count} > "
                f"{args.max_over_threshold_window_budget_count} at index {index}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
