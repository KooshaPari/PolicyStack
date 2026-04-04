#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"B95 signature preflight integrity gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_int(value, field):
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"invalid int for {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checks-csv", required=True)
    parser.add_argument("--failures-col", default="signature_failures")
    parser.add_argument("--max-failures", type=int, default=0)
    args = parser.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.checks_csv).read_text().splitlines()))
    if not rows:
        fail("checks-csv empty")

    failures = sum(parse_int(r.get(args.failures_col, 0), args.failures_col) for r in rows)
    if failures > args.max_failures:
        fail(f"total_failures={failures}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
