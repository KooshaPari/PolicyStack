#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E119 [lane B] capa reclaim efficiency gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--requested-key", default="requested")
    parser.add_argument("--reclaim-ms-key", default="reclaim_ms")
    parser.add_argument("--max-average-reclaim-ms", type=float, default=0.0)
    parser.add_argument("--min-efficiency-ratio", type=float, default=0.0)
    parser.add_argument("--min-window-efficiency-ratio", type=float, default=0.0)
    parser.add_argument("--timeout-flag-key", default="timed_out")
    parser.add_argument("--max-timeout-count", type=int, default=0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_reclaimed = 0.0
    total_requested = 0.0
    total_reclaim_ms = 0.0
    timeout_count = 0
    window_reclaimed: dict[str, float] = {}
    window_requested: dict[str, float] = {}

    for row in records:
        reclaimed = parse_float(row.get(args.reclaimed_key), args.reclaimed_key)
        requested = parse_float(row.get(args.requested_key), args.requested_key)
        reclaim_ms = parse_float(row.get(args.reclaim_ms_key, 0), args.reclaim_ms_key)
        timed_out = parse_int(row.get(args.timeout_flag_key, 0), args.timeout_flag_key)

        total_reclaimed += reclaimed
        total_requested += requested
        total_reclaim_ms += reclaim_ms
        timeout_count += 1 if timed_out else 0

        window = str(row.get(args.window_key, "default"))
        window_reclaimed[window] = window_reclaimed.get(window, 0.0) + reclaimed
        window_requested[window] = window_requested.get(window, 0.0) + requested

    if total_requested <= 0:
        fail(f"requested_total={total_requested} must be > 0")

    efficiency_ratio = total_reclaimed / total_requested
    if efficiency_ratio < args.min_efficiency_ratio:
        fail(f"efficiency_ratio={efficiency_ratio} < min_efficiency_ratio={args.min_efficiency_ratio}")

    average_reclaim_ms = total_reclaim_ms / len(records)
    if average_reclaim_ms > args.max_average_reclaim_ms:
        fail(
            f"average_reclaim_ms={average_reclaim_ms} > max_average_reclaim_ms="
            f"{args.max_average_reclaim_ms}"
        )

    if timeout_count > args.max_timeout_count:
        fail(f"timeout_count={timeout_count} > max_timeout_count={args.max_timeout_count}")

    for window in sorted(window_requested):
        requested = window_requested[window]
        if requested <= 0:
            fail(f"window={window} requested_total={requested} must be > 0")
        ratio = window_reclaimed[window] / requested
        if ratio < args.min_window_efficiency_ratio:
            fail(
                f"window={window} efficiency_ratio={ratio} < min_window_efficiency_ratio="
                f"{args.min_window_efficiency_ratio}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
