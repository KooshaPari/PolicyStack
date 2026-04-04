#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E118 [lane B] scheduler backpressure regression gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--pressure-key", default="pressure")
    parser.add_argument("--rejections-key", default="rejections")
    parser.add_argument("--max-average-pressure", type=float, default=0.0)
    parser.add_argument("--max-pressure", type=float, default=0.0)
    parser.add_argument("--max-total-rejections", type=int, default=0)
    parser.add_argument("--pressure-threshold", type=float, default=0.0)
    parser.add_argument("--max-threshold-breach-count", type=int, default=0)
    parser.add_argument("--max-window-average-pressure", type=float, default=0.0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_pressure = 0.0
    max_pressure = 0.0
    total_rejections = 0
    breach_count = 0
    window_totals: dict[str, float] = {}
    window_counts: dict[str, int] = {}

    for row in records:
        pressure = parse_float(row.get(args.pressure_key), args.pressure_key)
        rejections = parse_int(row.get(args.rejections_key, 0), args.rejections_key)
        total_pressure += pressure
        max_pressure = max(max_pressure, pressure)
        total_rejections += rejections
        if pressure > args.pressure_threshold:
            breach_count += 1

        window = str(row.get(args.window_key, "default"))
        window_totals[window] = window_totals.get(window, 0.0) + pressure
        window_counts[window] = window_counts.get(window, 0) + 1

    average_pressure = total_pressure / len(records)
    if average_pressure > args.max_average_pressure:
        fail(
            f"average_pressure={average_pressure} > max_average_pressure={args.max_average_pressure}"
        )

    if max_pressure > args.max_pressure:
        fail(f"max_pressure={max_pressure} > max_pressure={args.max_pressure}")

    if total_rejections > args.max_total_rejections:
        fail(
            f"total_rejections={total_rejections} > max_total_rejections={args.max_total_rejections}"
        )

    if breach_count > args.max_threshold_breach_count:
        fail(
            f"threshold_breach_count={breach_count} > max_threshold_breach_count="
            f"{args.max_threshold_breach_count}"
        )

    for window, count in sorted(window_counts.items()):
        average = window_totals[window] / count
        if average > args.max_window_average_pressure:
            fail(
                f"window={window} average_pressure={average} > max_window_average_pressure="
                f"{args.max_window_average_pressure}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
