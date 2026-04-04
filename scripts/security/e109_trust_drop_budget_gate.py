#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E109 trust drop budget gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(v, field: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transitions", required=True)
    parser.add_argument("--score-col", default="trust_score")
    parser.add_argument("--max-drop", type=float, default=0.0)
    args = parser.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.transitions).read_text().splitlines()))
    if not rows:
        fail("transitions payload must contain rows")

    drops = 0
    prev = parse_float(rows[0].get(args.score_col), args.score_col)
    for row in rows[1:]:
        score = parse_float(row.get(args.score_col), args.score_col)
        if prev - score > args.max_drop:
            drops += 1
        prev = score

    if drops:
        fail(f"trust_score_drops={drops}, max_drop={args.max_drop}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
