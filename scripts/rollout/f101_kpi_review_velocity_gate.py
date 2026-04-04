#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"F101 kpi review velocity gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_int(v, field):
    try:
        return int(v)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kpi", required=True)
    parser.add_argument("--velocity-col", default="reviews_per_day")
    parser.add_argument("--max-review-velocity-drop", type=float, default=0.0)
    args = parser.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.kpi).read_text().splitlines()))
    if len(rows) < 2:
        fail("insufficient kpi rows")

    values = [parse_int(r.get(args.velocity_col), args.velocity_col) for r in rows]
    drops = [a - b for a, b in zip(values, values[1:]) if a > b]
    max_drop = max(drops) if drops else 0
    if max_drop > args.max_review_velocity_drop:
        fail(f"max_review_velocity_drop={max_drop}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
