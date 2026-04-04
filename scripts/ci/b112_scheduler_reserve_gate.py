#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"B112 scheduler reserve gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_int(value, field):
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"invalid integer value for {field}: {value!r}")


def parse_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid numeric value for {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue-csv", required=True)
    parser.add_argument("--queue-col", default="queue_size")
    parser.add_argument("--utilization-col", default="utilization")
    parser.add_argument("--min-rows", type=int, default=1)
    parser.add_argument("--max-mean-queue", type=float, default=0.0)
    parser.add_argument("--min-headroom", type=float, default=0.0)
    parser.add_argument("--max-samples", type=int, default=0)
    args = parser.parse_args()

    try:
        rows = list(csv.DictReader(pathlib.Path(args.queue_csv).read_text().splitlines()))
    except Exception as exc:
        fail(f"invalid queue-csv: {exc}")

    if len(rows) < args.min_rows:
        fail(f"queue csv rows={len(rows)} < min_rows={args.min_rows}")

    samples = [row for row in rows if args.queue_col in row and args.utilization_col in row]
    if not samples:
        fail("no usable queue rows found")

    queue_sizes = [parse_int(row.get(args.queue_col, 0), args.queue_col) for row in samples]
    utilizations = [parse_float(row.get(args.utilization_col, 0.0), args.utilization_col) for row in samples]

    if args.max_samples and len(samples) > args.max_samples:
        queue_sizes = queue_sizes[: args.max_samples]
        utilizations = utilizations[: args.max_samples]

    mean_queue = sum(queue_sizes) / len(queue_sizes)
    if mean_queue > args.max_mean_queue:
        fail(f"mean_queue_size={mean_queue} > max_mean_queue={args.max_mean_queue}")

    headroom = min(utilizations)
    if headroom < args.min_headroom:
        fail(f"min_headroom={headroom} < min_headroom={args.min_headroom}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
