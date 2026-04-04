#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E147 custody activity regression budget gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--activity-col", default="activity")
    parser.add_argument("--drop-threshold", type=float, default=0.0)
    parser.add_argument("--max-regressions", type=int, default=0)
    parser.add_argument("--max-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-total-regression-drop", type=float, default=0.0)
    args = parser.parse_args()

    if args.max_regressions < 0:
        fail(f"max-regressions must be non-negative: {args.max_regressions}")
    if args.max_regression_rate < 0 or args.max_regression_rate > 1:
        fail(f"max-regression-rate must be between 0 and 1: {args.max_regression_rate}")
    if args.max_total_regression_drop < 0:
        fail(f"max-total-regression-drop must be non-negative: {args.max_total_regression_drop}")

    rows = load_rows(pathlib.Path(args.records))
    if not rows:
        fail("records payload must contain rows")

    regressions = 0
    regression_drop = 0.0
    row_count = 0
    previous_activity = None

    for row in rows:
        if not isinstance(row, dict):
            continue

        row_count += 1
        current = parse_float(row.get(args.activity_col), args.activity_col)
        if previous_activity is None:
            previous_activity = current
            continue

        activity_delta = current - previous_activity
        previous_activity = current
        if activity_delta <= -args.drop_threshold:
            regressions += 1
            regression_drop += -activity_delta

    if row_count == 0:
        fail("records payload must contain dict rows")

    regression_rate = regressions / row_count
    if regressions > args.max_regressions:
        fail(f"regressions={regressions} exceeds max_regressions={args.max_regressions}")
    if regression_rate > args.max_regression_rate:
        fail(
            f"regression_rate={regression_rate:.6f} exceeds max_regression_rate={args.max_regression_rate}"
        )
    if regression_drop > args.max_total_regression_drop:
        fail(
            "total_regression_drop="
            f"{regression_drop:.6f} exceeds max_total_regression_drop={args.max_total_regression_drop}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
