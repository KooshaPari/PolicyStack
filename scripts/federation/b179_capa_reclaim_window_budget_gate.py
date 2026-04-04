#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E179 [lane B] capa pressure budget gate failed: {message}",
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
    parser.add_argument("--samples-key", default="samples")
    parser.add_argument("--pressure-key", default="pressure")
    parser.add_argument("--pressure-budget-used-key", default="pressure_budget_used")
    parser.add_argument("--pressure-budget-total-key", default="pressure_budget_total")
    parser.add_argument("--pressure-overrun-events-key", default="pressure_overrun_events")
    parser.add_argument("--pressure-throttle-events-key", default="pressure_throttle_events")
    parser.add_argument("--min-total-samples", type=float, default=1.0)
    parser.add_argument("--max-average-pressure", type=float, default=0.0)
    parser.add_argument("--max-window-average-pressure", type=float, default=0.0)
    parser.add_argument("--max-pressure", type=float, default=0.0)
    parser.add_argument("--max-total-pressure-overrun-events", type=int, default=0)
    parser.add_argument("--max-total-pressure-throttle-events", type=int, default=0)
    parser.add_argument("--max-total-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-window-budget-usage-ratio", type=float, default=0.0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_samples = 0.0
    total_pressure = 0.0
    max_pressure = 0.0
    total_overrun_events = 0
    total_throttle_events = 0
    total_budget_used = 0.0
    total_budget_total = 0.0
    window_samples: dict[str, float] = {}
    window_pressure_totals: dict[str, float] = {}
    window_pressure_max: dict[str, float] = {}
    window_budget_used: dict[str, float] = {}
    window_budget_total: dict[str, float] = {}

    for row in records:
        samples = parse_float(row.get(args.samples_key), args.samples_key)
        pressure = parse_float(row.get(args.pressure_key), args.pressure_key)
        overrun_events = parse_int(
            row.get(args.pressure_overrun_events_key, 0),
            args.pressure_overrun_events_key,
        )
        throttle_events = parse_int(
            row.get(args.pressure_throttle_events_key, 0),
            args.pressure_throttle_events_key,
        )
        budget_used = parse_float(
            row.get(args.pressure_budget_used_key),
            args.pressure_budget_used_key,
        )
        budget_total = parse_float(
            row.get(args.pressure_budget_total_key),
            args.pressure_budget_total_key,
        )

        if samples < 0:
            fail(f"samples for {args.samples_key} must be >= 0; got {samples}")
        if pressure < 0:
            fail(f"pressure for {args.pressure_key} must be >= 0; got {pressure}")
        if overrun_events < 0:
            fail(
                f"pressure_overrun_events for {args.pressure_overrun_events_key} must be >= 0; "
                f"got {overrun_events}"
            )
        if throttle_events < 0:
            fail(
                f"pressure_throttle_events for {args.pressure_throttle_events_key} must be >= 0; "
                f"got {throttle_events}"
            )
        if budget_used < 0:
            fail(f"pressure_budget_used for {args.pressure_budget_used_key} must be >= 0; got {budget_used}")
        if budget_total <= 0:
            fail(
                f"pressure_budget_total for {args.pressure_budget_total_key} must be > 0; "
                f"got {budget_total}"
            )
        if budget_used > budget_total:
            fail(
                f"pressure_budget_used={budget_used} cannot exceed "
                f"pressure_budget_total={budget_total}"
            )

        total_samples += samples
        total_pressure += pressure * samples if samples else pressure
        max_pressure = max(max_pressure, pressure)
        total_overrun_events += overrun_events
        total_throttle_events += throttle_events
        total_budget_used += budget_used
        total_budget_total += budget_total

        window = str(row.get(args.window_key, "default"))
        window_samples[window] = window_samples.get(window, 0.0) + samples
        window_pressure_totals[window] = window_pressure_totals.get(window, 0.0) + (
            pressure * samples
        )
        window_pressure_max[window] = max(window_pressure_max.get(window, 0.0), pressure)
        window_budget_used[window] = window_budget_used.get(window, 0.0) + budget_used
        window_budget_total[window] = window_budget_total.get(window, 0.0) + budget_total

    if total_samples < args.min_total_samples:
        fail(f"total_samples={total_samples} < min_total_samples={args.min_total_samples}")

    if total_samples <= 0:
        fail(f"total_samples={total_samples} must be > 0")

    average_pressure = total_pressure / total_samples
    if average_pressure > args.max_average_pressure:
        fail(
            f"average_pressure={average_pressure} > max_average_pressure="
            f"{args.max_average_pressure}"
        )

    if max_pressure > args.max_pressure:
        fail(f"max_pressure={max_pressure} > max_pressure={args.max_pressure}")

    if total_budget_total <= 0:
        fail(f"total_pressure_budget_total={total_budget_total} must be > 0")

    total_budget_usage_ratio = total_budget_used / total_budget_total
    if total_budget_usage_ratio > args.max_total_budget_usage_ratio:
        fail(
            f"total_budget_usage_ratio={total_budget_usage_ratio} > "
            f"max_total_budget_usage_ratio={args.max_total_budget_usage_ratio}"
        )

    if total_overrun_events > args.max_total_pressure_overrun_events:
        fail(
            f"total_pressure_overrun_events={total_overrun_events} > "
            f"max_total_pressure_overrun_events={args.max_total_pressure_overrun_events}"
        )

    if total_throttle_events > args.max_total_pressure_throttle_events:
        fail(
            f"total_pressure_throttle_events={total_throttle_events} > "
            f"max_total_pressure_throttle_events={args.max_total_pressure_throttle_events}"
        )

    for window in sorted(window_samples):
        samples = window_samples[window]
        if samples <= 0:
            fail(f"window={window} samples={samples} must be > 0")

        window_average_pressure = window_pressure_totals[window] / samples
        if window_average_pressure > args.max_window_average_pressure:
            fail(
                f"window={window} average_pressure={window_average_pressure} > "
                f"max_window_average_pressure={args.max_window_average_pressure}"
            )

        window_total = window_budget_total[window]
        if window_total <= 0:
            fail(f"window={window} pressure_budget_total={window_total} must be > 0")
        window_budget_usage_ratio = window_budget_used[window] / window_total
        if window_budget_usage_ratio > args.max_window_budget_usage_ratio:
            fail(
                f"window={window} budget_usage_ratio={window_budget_usage_ratio} > "
                f"max_window_budget_usage_ratio={args.max_window_budget_usage_ratio}"
            )

        if window_pressure_max[window] > args.max_pressure:
            fail(f"window={window} max_pressure={window_pressure_max[window]} > max_pressure={args.max_pressure}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
