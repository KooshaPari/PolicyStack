#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E123 custody gap regression gate failed: {message}", file=sys.stderr)
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


def is_regression_row(
    row: dict,
    previous_row: dict | None,
    gap_col: str,
    gap_threshold: float,
    regression_delta: float,
) -> bool:
    gap_value = parse_float(row.get(gap_col), gap_col)
    if gap_value > gap_threshold:
        return True

    if previous_row is None:
        return False

    previous_gap = parse_float(previous_row.get(gap_col), gap_col)
    return (gap_value - previous_gap) >= regression_delta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", required=True)
    parser.add_argument("--gap-col", default="gap_seconds")
    parser.add_argument("--gap-threshold", type=float, default=300.0)
    parser.add_argument("--regression-delta", type=float, default=60.0)
    parser.add_argument("--max-regressions", type=int, default=0)
    args = parser.parse_args()

    if args.regression_delta < 0:
        fail(f"regression-delta must be non-negative: {args.regression_delta}")
    if args.max_regressions < 0:
        fail(f"max-regressions must be non-negative: {args.max_regressions}")

    rows = load_rows(pathlib.Path(args.records))
    if not rows:
        fail("records payload must contain rows")

    regressions = 0
    dict_rows_seen = 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        dict_rows_seen += 1
        previous = rows[index - 1] if index > 0 and isinstance(rows[index - 1], dict) else None
        if is_regression_row(row, previous, args.gap_col, args.gap_threshold, args.regression_delta):
            regressions += 1

    if dict_rows_seen == 0:
        fail("records payload must contain dict rows")

    if regressions > args.max_regressions:
        fail(f"regressions={regressions} exceeds max_regressions={args.max_regressions}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
