#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"D101 override resilience slope gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(v, field):
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resilience-csv", required=True)
    parser.add_argument("--time-field", default="window_start")
    parser.add_argument("--value-field", default="resilience_score")
    parser.add_argument("--max-downward-slope", type=float, default=0.0)
    parser.add_argument("--max-consecutive-drops", type=int, default=0)
    args = parser.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.resilience_csv).read_text().splitlines()))
    ordered = sorted(rows, key=lambda r: str(r.get(args.time_field, "")))
    values = [to_float(r.get(args.value_field), args.value_field) for r in ordered]
    if len(values) < 2:
        fail("insufficient rows")

    drops = [a - b for a, b in zip(values, values[1:]) if a > b]
    if not drops:
        return 0
    max_slope = max(drops)
    consecutive = 0
    max_consecutive = 0
    for d in drops:
        if d > 0:
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0

    if max_slope > args.max_downward_slope or max_consecutive > args.max_consecutive_drops:
        fail(f"max_slope={max_slope} max_consecutive_drops={max_consecutive}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
