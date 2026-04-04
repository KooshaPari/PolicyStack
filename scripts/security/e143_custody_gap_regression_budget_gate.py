#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E143 custody gap regression budget gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(value: object, field: str) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {value!r}")


def load_rows(path: pathlib.Path) -> list[dict]:
    try:
        if path.suffix.lower() == ".csv":
            return list(csv.DictReader(path.read_text().splitlines()))
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid custody input: {exc}")

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("records", "items", "entries", "transitions", "attestations"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
    fail("custody payload must be list or object with records/items/entries/transitions/attestations")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", required=True)
    parser.add_argument("--gap-col", default="gap_seconds")
    parser.add_argument("--increase-threshold", type=float, default=0.0)
    parser.add_argument("--max-regressions", type=int, default=0)
    parser.add_argument("--max-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-total-regression-increase", type=float, default=0.0)
    args = parser.parse_args()

    if args.max_regressions < 0:
        fail(f"max-regressions must be non-negative: {args.max_regressions}")
    if args.max_regression_rate < 0 or args.max_regression_rate > 1:
        fail(f"max-regression-rate must be between 0 and 1: {args.max_regression_rate}")
    if args.max_total_regression_increase < 0:
        fail(
            "max-total-regression-increase must be non-negative: "
            f"{args.max_total_regression_increase}"
        )

    rows = load_rows(pathlib.Path(args.records))
    if not rows:
        fail("records payload must contain rows")

    gap_values = []
    for row in rows:
        if isinstance(row, dict):
            gap_values.append(parse_float(row.get(args.gap_col), args.gap_col))

    if not gap_values:
        fail("records payload must contain dict rows with gap values")

    regressions = 0
    regression_increase = 0.0
    for previous_gap, current_gap in zip(gap_values, gap_values[1:]):
        increase = current_gap - previous_gap
        if increase >= args.increase_threshold:
            regressions += 1
            regression_increase += increase

    regression_rate = regressions / len(gap_values)
    if regressions > args.max_regressions:
        fail(f"regressions={regressions} exceeds max_regressions={args.max_regressions}")
    if regression_rate > args.max_regression_rate:
        fail(
            f"regression_rate={regression_rate:.6f} exceeds max_regression_rate={args.max_regression_rate}"
        )
    if regression_increase > args.max_total_regression_increase:
        fail(
            "total_regression_increase="
            f"{regression_increase:.6f} exceeds max_total_regression_increase="
            f"{args.max_total_regression_increase}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
