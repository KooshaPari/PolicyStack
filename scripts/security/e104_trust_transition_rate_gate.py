#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E104 trust transition rate gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(v, field):
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transitions", required=True)
    parser.add_argument("--rate-col", default="drift_rate")
    parser.add_argument("--max-rate", type=float, default=0.0)
    args = parser.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.transitions).read_text().splitlines()))
    if not rows:
        fail("transitions payload must contain rows")

    highest = 0.0
    for row in rows:
        rate = parse_float(row.get(args.rate_col, 0.0), args.rate_col)
        if rate > highest:
            highest = rate

    if highest > args.max_rate:
        fail(f"max_transition_rate={highest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
