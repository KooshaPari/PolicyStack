#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"B98 policy regression gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_int(value, field):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        fail(f"invalid integer for {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checks-csv", required=True)
    parser.add_argument("--outcome-col", default="outcome")
    parser.add_argument("--count-col", default="count")
    parser.add_argument("--fail-on", default="fail")
    parser.add_argument("--max-fail-count", type=int, default=0)
    args = parser.parse_args()

    try:
        rows = list(csv.DictReader(pathlib.Path(args.checks_csv).read_text().splitlines()))
    except Exception as exc:
        fail(f"invalid checks csv: {exc}")
    if not rows:
        fail("checks-csv empty")

    fail_rows = []
    total_fail_count = 0
    for row in rows:
        if row.get(args.outcome_col) == args.fail_on:
            fail_rows.append(row)
            total_fail_count += parse_int(row.get(args.count_col, 0), args.count_col)

    if total_fail_count > args.max_fail_count:
        fail(f"fail_count={total_fail_count} rows={len(fail_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
