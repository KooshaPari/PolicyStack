#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E131 [lane B] capa reclaim window gate failed: {message}",
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
    parser.add_argument("--reclaimed-key", default="reclaimed")
    parser.add_argument("--reclaimable-key", default="reclaimable")
    parser.add_argument("--reclaim-latency-ms-key", default="reclaim_latency_ms")
    parser.add_argument("--timeout-flag-key", default="timed_out")
    parser.add_argument("--min-total-reclaim-ratio", type=float, default=0.0)
    parser.add_argument("--min-window-reclaim-ratio", type=float, default=0.0)
    parser.add_argument("--max-average-reclaim-latency-ms", type=float, default=0.0)
    parser.add_argument("--max-window-average-reclaim-latency-ms", type=float, default=0.0)
    parser.add_argument("--max-timeout-count", type=int, default=0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_reclaimed = 0.0
    total_reclaimable = 0.0
    latency_total = 0.0
    timeout_count = 0
    window_reclaimed: dict[str, float] = {}
    window_reclaimable: dict[str, float] = {}
    window_latency_totals: dict[str, float] = {}
    window_counts: dict[str, int] = {}

    for row in records:
        reclaimed = parse_float(row.get(args.reclaimed_key), args.reclaimed_key)
        reclaimable = parse_float(row.get(args.reclaimable_key), args.reclaimable_key)
        reclaim_latency = parse_float(
            row.get(args.reclaim_latency_ms_key, 0),
            args.reclaim_latency_ms_key,
        )
        timed_out = parse_int(row.get(args.timeout_flag_key, 0), args.timeout_flag_key)

        if reclaimed < 0:
            fail(f"reclaimed for {args.reclaimed_key} must be >= 0; got {reclaimed}")
        if reclaimable < 0:
            fail(f"reclaimable for {args.reclaimable_key} must be >= 0; got {reclaimable}")
        if reclaimed > reclaimable:
            fail(f"reclaimed={reclaimed} cannot exceed reclaimable={reclaimable}")
        if reclaim_latency < 0:
            fail(
                f"reclaim latency for {args.reclaim_latency_ms_key} must be >= 0; got "
                f"{reclaim_latency}"
            )

        total_reclaimed += reclaimed
        total_reclaimable += reclaimable
        latency_total += reclaim_latency
        timeout_count += 1 if timed_out else 0

        window = str(row.get(args.window_key, "default"))
        window_reclaimed[window] = window_reclaimed.get(window, 0.0) + reclaimed
        window_reclaimable[window] = window_reclaimable.get(window, 0.0) + reclaimable
        window_latency_totals[window] = window_latency_totals.get(window, 0.0) + reclaim_latency
        window_counts[window] = window_counts.get(window, 0) + 1

    if total_reclaimable <= 0:
        fail("total_reclaimable must be > 0")
    total_reclaim_ratio = total_reclaimed / total_reclaimable
    if total_reclaim_ratio < args.min_total_reclaim_ratio:
        fail(
            f"total_reclaim_ratio={total_reclaim_ratio} < min_total_reclaim_ratio="
            f"{args.min_total_reclaim_ratio}"
        )

    average_reclaim_latency = latency_total / len(records)
    if average_reclaim_latency > args.max_average_reclaim_latency_ms:
        fail(
            f"average_reclaim_latency_ms={average_reclaim_latency} > "
            f"max_average_reclaim_latency_ms={args.max_average_reclaim_latency_ms}"
        )

    if timeout_count > args.max_timeout_count:
        fail(f"timeout_count={timeout_count} > max_timeout_count={args.max_timeout_count}")

    for window in sorted(window_counts):
        reclaimable = window_reclaimable[window]
        if reclaimable <= 0:
            fail(f"window={window} reclaimable={reclaimable} must be > 0")
        reclaim_ratio = window_reclaimed[window] / reclaimable
        if reclaim_ratio < args.min_window_reclaim_ratio:
            fail(
                f"window={window} reclaim_ratio={reclaim_ratio} < "
                f"min_window_reclaim_ratio={args.min_window_reclaim_ratio}"
            )

        window_average_latency = window_latency_totals[window] / window_counts[window]
        if window_average_latency > args.max_window_average_reclaim_latency_ms:
            fail(
                f"window={window} average_reclaim_latency_ms={window_average_latency} > "
                f"max_window_average_reclaim_latency_ms={args.max_window_average_reclaim_latency_ms}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
