#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"D103 suppression decay plateau gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(v, field):
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suppression-csv", required=True)
    parser.add_argument("--value-field", default="suppression_level")
    parser.add_argument("--min-decay", type=float, default=0.0)
    parser.add_argument("--max-plateau", type=int, default=0)
    args = parser.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.suppression_csv).read_text().splitlines()))
    values = [to_float(r.get(args.value_field), args.value_field) for r in rows]
    if len(values) < 2:
        fail("insufficient suppression rows")

    deltas = [abs(a - b) for a, b in zip(values, values[1:])]
    plateau = sum(1 for d in deltas if d <= args.min_decay)
    if plateau > args.max_plateau:
        fail(f"plateau_windows={plateau}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
