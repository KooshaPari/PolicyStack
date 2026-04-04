#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E100 custody chain gap gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_int(v, field):
    try:
        return int(v)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--custody", required=True)
    parser.add_argument("--gap-col", default="gap_count")
    parser.add_argument("--max-gap-events", type=int, default=0)
    args = parser.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.custody).read_text().splitlines()))
    gaps = sum(parse_int(r.get(args.gap_col), args.gap_col) for r in rows)
    if gaps > args.max_gap_events:
        fail(f"custody_gaps={gaps}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
