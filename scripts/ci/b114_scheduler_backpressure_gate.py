#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"B114 scheduler backpressure gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid numeric value for {field}: {value!r}")


def parse_int(value, field):
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"invalid integer value for {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backpressure-csv", required=True)
    parser.add_argument("--time-col", default="time")
    parser.add_argument("--pressure-col", default="pressure")
    parser.add_argument("--reject-col", default="rejections")
    parser.add_argument("--max-pressure", type=float, default=0.0)
    parser.add_argument("--max-sample-reject-rate", type=float, default=0.0)
    parser.add_argument("--max-total-rejections", type=int, default=0)
    args = parser.parse_args()

    try:
        rows = list(csv.DictReader(pathlib.Path(args.backpressure_csv).read_text().splitlines()))
    except Exception as exc:
        fail(f"invalid backpressure csv: {exc}")

    if not rows:
        fail("backpressure-csv empty")

    total_rejects = 0
    max_pressure = 0.0
    for row in rows:
        pressure = parse_float(row.get(args.pressure_col), args.pressure_col)
        rejects = parse_int(row.get(args.reject_col), args.reject_col)
        total_rejects += rejects
        max_pressure = max(max_pressure, pressure)

    if max_pressure > args.max_pressure:
        fail(f"max_pressure={max_pressure} > max_pressure={args.max_pressure}")

    if args.max_sample_reject_rate > 0:
        sample_reject_rate = total_rejects / len(rows)
        if sample_reject_rate > args.max_sample_reject_rate:
            fail(
                f"reject_rate={sample_reject_rate} > max_sample_reject_rate="
                f"{args.max_sample_reject_rate}"
            )

    if total_rejects > args.max_total_rejections:
        fail(f"total_rejects={total_rejects} > max_total_rejections={args.max_total_rejections}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
