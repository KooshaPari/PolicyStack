#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"F106 KPI federation coverage gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _to_float(value: object, field: str) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kpi-csv", required=True)
    parser.add_argument("--coverage-column", default="coverage")
    parser.add_argument("--min-coverage", type=float, default=0.8)
    args = parser.parse_args()

    path = pathlib.Path(args.kpi_csv)
    rows = list(csv.DictReader(path.read_text().splitlines()))
    if not rows:
        fail("no KPI rows")

    coverages = [_to_float(r.get(args.coverage_column), args.coverage_column) for r in rows]
    below = [x for x in coverages if x < args.min_coverage]
    if below:
        fail(f"min_coverage={args.min_coverage} violated by {len(below)} rows")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
