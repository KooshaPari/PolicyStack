#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E215 custody gap window budget gate failed: {message}", file=sys.stderr)
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
    fail(
        "custody payload must be list or object with "
        "records/items/entries/transitions/attestations"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", required=True)
    parser.add_argument("--gap-col", default="gap_seconds")
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--max-total-gap-per-window", type=float, default=0.0)
    parser.add_argument("--max-average-gap-per-window", type=float, default=0.0)
    parser.add_argument("--max-gap-per-window", type=float, default=0.0)
    parser.add_argument("--max-window-violations", type=int, default=0)
    args = parser.parse_args()

    if args.window_size <= 0:
        fail(f"window-size must be positive: {args.window_size}")
    if args.max_total_gap_per_window < 0:
        fail(f"max-total-gap-per-window must be non-negative: {args.max_total_gap_per_window}")
    if args.max_average_gap_per_window < 0:
        fail(
            "max-average-gap-per-window must be non-negative: "
            f"{args.max_average_gap_per_window}"
        )
    if args.max_gap_per_window < 0:
        fail(f"max-gap-per-window must be non-negative: {args.max_gap_per_window}")
    if args.max_window_violations < 0:
        fail(f"max-window-violations must be non-negative: {args.max_window_violations}")

    rows = load_rows(pathlib.Path(args.records))
    if not rows:
        fail("records payload must contain rows")

    gap_values = []
    for row in rows:
        if isinstance(row, dict):
            gap_values.append(parse_float(row.get(args.gap_col), args.gap_col))

    if not gap_values:
        fail("records payload must contain dict rows with gap values")

    if args.window_size > len(gap_values):
        fail(f"window-size={args.window_size} exceeds available rows={len(gap_values)}")

    violations = 0
    for start in range(0, len(gap_values) - args.window_size + 1):
        window = gap_values[start : start + args.window_size]
        total_gap = sum(window)
        average_gap = total_gap / len(window)
        peak_gap = max(window)
        if (
            total_gap > args.max_total_gap_per_window
            or average_gap > args.max_average_gap_per_window
            or peak_gap > args.max_gap_per_window
        ):
            violations += 1

    if violations > args.max_window_violations:
        fail(
            f"window_violations={violations} exceeds max_window_violations="
            f"{args.max_window_violations}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
