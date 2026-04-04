#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E105 custody gap rate gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_int(v, field: str) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--custody", required=True)
    parser.add_argument("--gap-col", default="gap_count")
    parser.add_argument("--max-total-gap", type=int, default=0)
    args = parser.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.custody).read_text().splitlines()))
    total_gap = sum(parse_int(row.get(args.gap_col), args.gap_col) for row in rows)
    if total_gap > args.max_total_gap:
        fail(f"total_gap_count={total_gap}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
