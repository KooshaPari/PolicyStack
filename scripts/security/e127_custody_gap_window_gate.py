#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E127 custody gap window gate failed: {message}", file=sys.stderr)
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


def is_gap_violation(row: dict, gap_col: str, gap_threshold: float) -> bool:
    gap_value = parse_float(row.get(gap_col), gap_col)
    return gap_value > gap_threshold


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", required=True)
    parser.add_argument("--gap-col", default="gap_seconds")
    parser.add_argument("--gap-threshold", type=float, default=300.0)
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--max-gap-violations-per-window", type=int, default=0)
    parser.add_argument("--max-window-violations", type=int, default=0)
    args = parser.parse_args()

    if args.window_size <= 0:
        fail(f"window-size must be positive: {args.window_size}")
    if args.max_gap_violations_per_window < 0:
        fail(
            "max-gap-violations-per-window must be non-negative: "
            f"{args.max_gap_violations_per_window}"
        )
    if args.max_window_violations < 0:
        fail(f"max-window-violations must be non-negative: {args.max_window_violations}")

    rows = load_rows(pathlib.Path(args.records))
    if not rows:
        fail("records payload must contain rows")

    gap_flags = []
    for row in rows:
        if isinstance(row, dict):
            gap_flags.append(is_gap_violation(row, args.gap_col, args.gap_threshold))

    if not gap_flags:
        fail("records payload must contain dict rows")

    violations = 0
    for start in range(0, len(gap_flags) - args.window_size + 1):
        window = gap_flags[start : start + args.window_size]
        if sum(window) > args.max_gap_violations_per_window:
            violations += 1

    if violations > args.max_window_violations:
        fail(f"window_violations={violations} exceeds max_window_violations={args.max_window_violations}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
