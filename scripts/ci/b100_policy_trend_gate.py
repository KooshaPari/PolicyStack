#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"B100 policy trend gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid float for {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trend-csv", required=True)
    parser.add_argument("--value-col", default="value")
    parser.add_argument("--time-col", default="time")
    parser.add_argument("--max-negative-delta", type=float, default=0.0)
    args = parser.parse_args()

    try:
        rows = list(csv.DictReader(pathlib.Path(args.trend_csv).read_text().splitlines()))
    except Exception as exc:
        fail(f"invalid trend csv: {exc}")
    if not rows:
        fail("trend-csv empty")

    ordered_rows = sorted(rows, key=lambda row: row.get(args.time_col, ""))
    deltas = []
    prev = None
    for row in ordered_rows:
        current = parse_float(row.get(args.value_col, 0), args.value_col)
        if prev is not None:
            deltas.append(current - prev)
        prev = current

    worst_delta = min(deltas) if deltas else 0.0
    if worst_delta < -args.max_negative_delta:
        fail(f"worst_negative_delta={worst_delta} >max_allowed_negative={-args.max_negative_delta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
