#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E151 custody gap regression stability gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--max-regression-rate", type=float, default=0.0)
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--max-regressions-per-window", type=int, default=0)
    parser.add_argument("--max-window-violations", type=int, default=0)
    parser.add_argument("--min-stable-window-ratio", type=float, default=1.0)
    args = parser.parse_args()

    if args.regression_delta < 0:
        fail(f"regression-delta must be non-negative: {args.regression_delta}")
    if args.gap_threshold < 0:
        fail(f"gap-threshold must be non-negative: {args.gap_threshold}")
    if args.max_regressions < 0:
        fail(f"max-regressions must be non-negative: {args.max_regressions}")
    if args.max_regression_rate < 0 or args.max_regression_rate > 1:
        fail(f"max-regression-rate must be between 0 and 1: {args.max_regression_rate}")
    if args.window_size <= 0:
        fail(f"window-size must be positive: {args.window_size}")
    if args.max_regressions_per_window < 0:
        fail(
            "max-regressions-per-window must be non-negative: "
            f"{args.max_regressions_per_window}"
        )
    if args.max_window_violations < 0:
        fail(f"max-window-violations must be non-negative: {args.max_window_violations}")
    if args.min_stable_window_ratio < 0 or args.min_stable_window_ratio > 1:
        fail(
            "min-stable-window-ratio must be between 0 and 1: "
            f"{args.min_stable_window_ratio}"
        )

    rows = load_rows(pathlib.Path(args.records))
    if not rows:
        fail("records payload must contain rows")

    regression_flags = []
    dict_rows_seen = 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue

        dict_rows_seen += 1
        previous = rows[index - 1] if index > 0 and isinstance(rows[index - 1], dict) else None
        regression_flags.append(
            is_regression_row(
                row,
                previous,
                args.gap_col,
                args.gap_threshold,
                args.regression_delta,
            )
        )

    if not regression_flags:
        fail("records payload must contain dict rows")

    regressions = sum(regression_flags)
    regression_rate = regressions / len(regression_flags)
    if regressions > args.max_regressions:
        fail(f"regressions={regressions} exceeds max_regressions={args.max_regressions}")
    if regression_rate > args.max_regression_rate:
        fail(
            f"regression_rate={regression_rate:.6f} exceeds max_regression_rate={args.max_regression_rate}"
        )

    if args.window_size > len(regression_flags):
        fail(
            f"window-size={args.window_size} exceeds available rows={len(regression_flags)}"
        )

    window_count = len(regression_flags) - args.window_size + 1
    violations = 0
    for start in range(window_count):
        window = regression_flags[start : start + args.window_size]
        if sum(window) > args.max_regressions_per_window:
            violations += 1

    stable_ratio = (window_count - violations) / window_count
    if violations > args.max_window_violations:
        fail(
            f"window_violations={violations} exceeds max_window_violations={args.max_window_violations}"
        )
    if stable_ratio < args.min_stable_window_ratio:
        fail(
            f"stable_window_ratio={stable_ratio:.6f} below min_stable_window_ratio="
            f"{args.min_stable_window_ratio}"
        )

    if dict_rows_seen == 0:
        fail("records payload must contain dict rows")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
