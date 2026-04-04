#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E131 custody gap regression rate gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--regression-col", default="gap_delta")
    parser.add_argument("--regression-threshold", type=float, default=0.0)
    parser.add_argument("--max-regression-rate", type=float, default=0.0)
    args = parser.parse_args()

    if args.max_regression_rate < 0 or args.max_regression_rate > 1:
        fail(f"max-regression-rate must be between 0 and 1: {args.max_regression_rate}")

    rows = load_rows(pathlib.Path(args.records))
    if not rows:
        fail("records payload must contain rows")

    regression_flags = []
    previous_gap = None
    for row in rows:
        if not isinstance(row, dict):
            continue

        regression_value = row.get(args.regression_col)
        if regression_value is not None and str(regression_value).strip() != "":
            regression_flags.append(
                parse_float(regression_value, args.regression_col) > args.regression_threshold
            )
            continue

        gap_value = parse_float(row.get(args.gap_col), args.gap_col)
        if previous_gap is None:
            regression_flags.append(False)
        else:
            regression_flags.append((gap_value - previous_gap) > args.regression_threshold)
        previous_gap = gap_value

    if not regression_flags:
        fail("records payload must contain dict rows")

    regressions = sum(regression_flags)
    regression_rate = regressions / len(regression_flags)
    if regression_rate > args.max_regression_rate:
        fail(
            f"regression_rate={regression_rate:.6f} exceeds max_regression_rate={args.max_regression_rate}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
