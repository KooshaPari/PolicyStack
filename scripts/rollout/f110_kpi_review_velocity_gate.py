#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"F110 KPI review velocity gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _to_float(value: object, field: str) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kpi-csv", required=True)
    parser.add_argument("--velocity-column", default="velocity")
    parser.add_argument("--min-velocity", type=float, default=0.9)
    args = parser.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.kpi_csv).read_text().splitlines()))
    if not rows:
        fail("no KPI rows")

    velocities = [
        _to_float(row.get(args.velocity_column), args.velocity_column)
        for row in rows
    ]
    below = [x for x in velocities if x < args.min_velocity]
    if below:
        fail(f"min_velocity={args.min_velocity} violated by {len(below)} rows")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
