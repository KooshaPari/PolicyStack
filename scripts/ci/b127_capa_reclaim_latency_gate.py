#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E127 [lane B] capa reclaim latency gate failed: {message}",
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
    parser.add_argument("--reclaim-latency-ms-key", default="reclaim_latency_ms")
    parser.add_argument("--p95-reclaim-latency-ms-key", default="p95_reclaim_latency_ms")
    parser.add_argument("--timeout-flag-key", default="timed_out")
    parser.add_argument("--max-average-reclaim-latency-ms", type=float, default=0.0)
    parser.add_argument("--max-p95-reclaim-latency-ms", type=float, default=0.0)
    parser.add_argument("--max-window-average-reclaim-latency-ms", type=float, default=0.0)
    parser.add_argument("--latency-threshold-ms", type=float, default=0.0)
    parser.add_argument("--max-threshold-breach-count", type=int, default=0)
    parser.add_argument("--max-timeout-count", type=int, default=0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    latency_total = 0.0
    max_p95_latency = 0.0
    threshold_breach_count = 0
    timeout_count = 0
    window_totals: dict[str, float] = {}
    window_counts: dict[str, int] = {}

    for row in records:
        reclaim_latency = parse_float(
            row.get(args.reclaim_latency_ms_key),
            args.reclaim_latency_ms_key,
        )
        p95_reclaim_latency = parse_float(
            row.get(args.p95_reclaim_latency_ms_key, reclaim_latency),
            args.p95_reclaim_latency_ms_key,
        )
        timed_out = parse_int(row.get(args.timeout_flag_key, 0), args.timeout_flag_key)

        latency_total += reclaim_latency
        max_p95_latency = max(max_p95_latency, p95_reclaim_latency)
        if reclaim_latency > args.latency_threshold_ms:
            threshold_breach_count += 1
        timeout_count += 1 if timed_out else 0

        window = str(row.get(args.window_key, "default"))
        window_totals[window] = window_totals.get(window, 0.0) + reclaim_latency
        window_counts[window] = window_counts.get(window, 0) + 1

    average_reclaim_latency = latency_total / len(records)
    if average_reclaim_latency > args.max_average_reclaim_latency_ms:
        fail(
            f"average_reclaim_latency_ms={average_reclaim_latency} > "
            f"max_average_reclaim_latency_ms={args.max_average_reclaim_latency_ms}"
        )

    if max_p95_latency > args.max_p95_reclaim_latency_ms:
        fail(
            f"max_p95_reclaim_latency_ms={max_p95_latency} > max_p95_reclaim_latency_ms="
            f"{args.max_p95_reclaim_latency_ms}"
        )

    if threshold_breach_count > args.max_threshold_breach_count:
        fail(
            f"threshold_breach_count={threshold_breach_count} > max_threshold_breach_count="
            f"{args.max_threshold_breach_count}"
        )

    if timeout_count > args.max_timeout_count:
        fail(f"timeout_count={timeout_count} > max_timeout_count={args.max_timeout_count}")

    for window, count in sorted(window_counts.items()):
        average = window_totals[window] / count
        if average > args.max_window_average_reclaim_latency_ms:
            fail(
                f"window={window} average_reclaim_latency_ms={average} > "
                f"max_window_average_reclaim_latency_ms={args.max_window_average_reclaim_latency_ms}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
