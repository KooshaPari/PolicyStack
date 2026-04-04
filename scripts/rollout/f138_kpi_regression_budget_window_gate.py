#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E138 kpi regression budget window gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--regression-budget-window-score-field", default="regression_budget_window_score")
    parser.add_argument("--max-regression-budget-window-score", type=float, default=0.0)
    parser.add_argument("--regression-budget-window-count-field", default="regression_budget_window_count")
    parser.add_argument("--max-regression-budget-window-count", type=int, default=0)
    args = parser.parse_args()

    records = load_records(pathlib.Path(args.kpi))
    for index, record in enumerate(records):
        regression_budget_window_score = to_float(
            record.get(args.regression_budget_window_score_field),
            args.regression_budget_window_score_field,
            index,
        )
        if regression_budget_window_score > args.max_regression_budget_window_score:
            fail(
                f"{args.regression_budget_window_score_field}={regression_budget_window_score} > "
                f"{args.max_regression_budget_window_score} at index {index}"
            )

        regression_budget_window_count = to_int(
            record.get(args.regression_budget_window_count_field),
            args.regression_budget_window_count_field,
            index,
        )
        if regression_budget_window_count > args.max_regression_budget_window_count:
            fail(
                f"{args.regression_budget_window_count_field}={regression_budget_window_count} > "
                f"{args.max_regression_budget_window_count} at index {index}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
