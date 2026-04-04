#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E130 [lane B] scheduler queue latency budget gate failed: {message}",
        file=sys.stderr,
    )
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


def infer_format(path: pathlib.Path, explicit_format: str) -> str:
    if explicit_format != "auto":
        return explicit_format
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".json":
        return "json"
    fail(f"cannot infer input format from suffix={path.suffix!r}; use --format")
    return "json"


def load_records(path: pathlib.Path, fmt: str, records_key: str) -> list[dict]:
    if fmt == "csv":
        try:
            rows = list(csv.DictReader(path.read_text().splitlines()))
        except Exception as exc:
            fail(f"invalid csv input: {exc}")
        if not rows:
            fail("input csv is empty")
        return rows

    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"invalid json input: {exc}")

    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        candidate = payload.get(records_key)
        if isinstance(candidate, list):
            rows = candidate
        else:
            rows = [payload]
    else:
        fail("json input must be an object or array")
        rows = []

    if not rows:
        fail("input json resolved to zero records")
    if not all(isinstance(row, dict) for row in rows):
        fail("all records must be JSON objects")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--format", choices=["auto", "csv", "json"], default="auto")
    parser.add_argument("--records-key", default="records")
    parser.add_argument("--window-key", default="window")
    parser.add_argument("--queue-latency-ms-key", default="queue_latency_ms")
    parser.add_argument("--p95-queue-latency-ms-key", default="p95_queue_latency_ms")
    parser.add_argument("--queue-depth-key", default="queue_depth")
    parser.add_argument("--budget-breach-flag-key", default="budget_breached")
    parser.add_argument("--max-average-queue-latency-ms", type=float, default=0.0)
    parser.add_argument("--max-p95-queue-latency-ms", type=float, default=0.0)
    parser.add_argument("--max-window-average-queue-latency-ms", type=float, default=0.0)
    parser.add_argument("--max-queue-depth", type=float, default=0.0)
    parser.add_argument("--max-budget-breach-count", type=int, default=0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    latency_total = 0.0
    max_p95_latency = 0.0
    max_queue_depth = 0.0
    budget_breach_count = 0
    window_latency_totals: dict[str, float] = {}
    window_counts: dict[str, int] = {}

    for row in records:
        queue_latency = parse_float(row.get(args.queue_latency_ms_key), args.queue_latency_ms_key)
        p95_queue_latency = parse_float(
            row.get(args.p95_queue_latency_ms_key, queue_latency),
            args.p95_queue_latency_ms_key,
        )
        queue_depth = parse_float(row.get(args.queue_depth_key, 0), args.queue_depth_key)
        budget_breached = parse_int(
            row.get(args.budget_breach_flag_key, 0),
            args.budget_breach_flag_key,
        )

        if queue_latency < 0:
            fail(f"queue latency for {args.queue_latency_ms_key} must be >= 0; got {queue_latency}")
        if p95_queue_latency < 0:
            fail(
                f"p95 queue latency for {args.p95_queue_latency_ms_key} must be >= 0; got "
                f"{p95_queue_latency}"
            )
        if queue_depth < 0:
            fail(f"queue depth for {args.queue_depth_key} must be >= 0; got {queue_depth}")

        latency_total += queue_latency
        max_p95_latency = max(max_p95_latency, p95_queue_latency)
        max_queue_depth = max(max_queue_depth, queue_depth)
        budget_breach_count += 1 if budget_breached else 0

        window = str(row.get(args.window_key, "default"))
        window_latency_totals[window] = window_latency_totals.get(window, 0.0) + queue_latency
        window_counts[window] = window_counts.get(window, 0) + 1

    average_queue_latency = latency_total / len(records)
    if average_queue_latency > args.max_average_queue_latency_ms:
        fail(
            f"average_queue_latency_ms={average_queue_latency} > max_average_queue_latency_ms="
            f"{args.max_average_queue_latency_ms}"
        )

    if max_p95_latency > args.max_p95_queue_latency_ms:
        fail(
            f"max_p95_queue_latency_ms={max_p95_latency} > max_p95_queue_latency_ms="
            f"{args.max_p95_queue_latency_ms}"
        )

    if max_queue_depth > args.max_queue_depth:
        fail(f"max_queue_depth={max_queue_depth} > max_queue_depth={args.max_queue_depth}")

    if budget_breach_count > args.max_budget_breach_count:
        fail(
            f"budget_breach_count={budget_breach_count} > "
            f"max_budget_breach_count={args.max_budget_breach_count}"
        )

    for window, count in sorted(window_counts.items()):
        window_average = window_latency_totals[window] / count
        if window_average > args.max_window_average_queue_latency_ms:
            fail(
                f"window={window} average_queue_latency_ms={window_average} > "
                f"max_window_average_queue_latency_ms={args.max_window_average_queue_latency_ms}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
