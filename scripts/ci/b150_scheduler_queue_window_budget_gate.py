#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E150 [lane B] scheduler queue window budget gate failed: {message}",
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
    parser.add_argument("--queue-regressions-key", default="queue_regressions")
    parser.add_argument("--queue-budget-used-key", default="queue_budget_used")
    parser.add_argument("--queue-budget-total-key", default="queue_budget_total")
    parser.add_argument("--queue-overflow-events-key", default="queue_overflow_events")
    parser.add_argument("--queue-stall-events-key", default="queue_stall_events")
    parser.add_argument("--min-total-samples", type=float, default=1.0)
    parser.add_argument("--max-total-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-window-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-window-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-total-regressions", type=int, default=0)
    parser.add_argument("--max-total-queue-overrun-events", type=int, default=0)
    parser.add_argument("--max-total-queue-stall-events", type=int, default=0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_samples = 0.0
    total_queue_regressions = 0
    total_queue_budget_used = 0.0
    total_queue_budget_total = 0.0
    total_queue_overflow_events = 0
    total_queue_stall_events = 0
    window_samples: dict[str, float] = {}
    window_regressions: dict[str, int] = {}
    window_queue_budget_used: dict[str, float] = {}
    window_queue_budget_total: dict[str, float] = {}

    for row in records:
        samples = parse_float(row.get(args.samples_key), args.samples_key)
        queue_regressions = parse_int(row.get(args.queue_regressions_key, 0), args.queue_regressions_key)
        queue_budget_used = parse_float(
            row.get(args.queue_budget_used_key),
            args.queue_budget_used_key,
        )
        queue_budget_total = parse_float(
            row.get(args.queue_budget_total_key),
            args.queue_budget_total_key,
        )
        queue_overflow_events = parse_int(
            row.get(args.queue_overflow_events_key, 0),
            args.queue_overflow_events_key,
        )
        queue_stall_events = parse_int(
            row.get(args.queue_stall_events_key, 0),
            args.queue_stall_events_key,
        )

        if samples < 0:
            fail(f"samples for {args.samples_key} must be >= 0; got {samples}")
        if queue_regressions < 0:
            fail(f"queue_regressions for {args.queue_regressions_key} must be >= 0; got {queue_regressions}")
        if queue_regressions > samples:
            fail(
                f"queue_regressions={queue_regressions} cannot exceed samples={samples}"
            )
        if queue_budget_used < 0:
            fail(
                f"queue_budget_used for {args.queue_budget_used_key} must be >= 0; got "
                f"{queue_budget_used}"
            )
        if queue_budget_total <= 0:
            fail(
                f"queue_budget_total for {args.queue_budget_total_key} must be > 0; got "
                f"{queue_budget_total}"
            )
        if queue_budget_used > queue_budget_total:
            fail(
                f"queue_budget_used={queue_budget_used} cannot exceed "
                f"queue_budget_total={queue_budget_total}"
            )
        if queue_overflow_events < 0:
            fail(
                f"queue_overflow_events for {args.queue_overflow_events_key} must be >= 0; "
                f"got {queue_overflow_events}"
            )
        if queue_stall_events < 0:
            fail(
                f"queue_stall_events for {args.queue_stall_events_key} must be >= 0; "
                f"got {queue_stall_events}"
            )

        total_samples += samples
        total_queue_regressions += queue_regressions
        total_queue_budget_used += queue_budget_used
        total_queue_budget_total += queue_budget_total
        total_queue_overflow_events += queue_overflow_events
        total_queue_stall_events += queue_stall_events

        window = str(row.get(args.window_key, "default"))
        window_samples[window] = window_samples.get(window, 0.0) + samples
        window_regressions[window] = window_regressions.get(window, 0) + queue_regressions
        window_queue_budget_used[window] = (
            window_queue_budget_used.get(window, 0.0) + queue_budget_used
        )
        window_queue_budget_total[window] = (
            window_queue_budget_total.get(window, 0.0) + queue_budget_total
        )

    if total_samples < args.min_total_samples:
        fail(f"total_samples={total_samples} < min_total_samples={args.min_total_samples}")

    if total_queue_budget_total <= 0:
        fail(f"total_queue_budget_total={total_queue_budget_total} must be > 0")

    total_budget_usage_ratio = total_queue_budget_used / total_queue_budget_total
    if total_budget_usage_ratio > args.max_total_budget_usage_ratio:
        fail(
            f"total_budget_usage_ratio={total_budget_usage_ratio} > "
            f"max_total_budget_usage_ratio={args.max_total_budget_usage_ratio}"
        )

    total_queue_regression_rate = total_queue_regressions / total_samples
    if total_queue_regression_rate > args.max_window_regression_rate:
        fail(
            f"total_queue_regression_rate={total_queue_regression_rate} > "
            f"max_window_regression_rate={args.max_window_regression_rate}"
        )

    if total_queue_overflow_events > args.max_total_queue_overrun_events:
        fail(
            f"total_queue_overflow_events={total_queue_overflow_events} > "
            f"max_total_queue_overrun_events={args.max_total_queue_overrun_events}"
        )

    if total_queue_stall_events > args.max_total_queue_stall_events:
        fail(
            f"total_queue_stall_events={total_queue_stall_events} > "
            f"max_total_queue_stall_events={args.max_total_queue_stall_events}"
        )

    if total_queue_regressions > args.max_total_regressions:
        fail(
            f"total_queue_regressions={total_queue_regressions} > "
            f"max_total_regressions={args.max_total_regressions}"
        )

    for window in sorted(window_samples):
        samples = window_samples[window]
        if samples <= 0:
            fail(f"window={window} samples={samples} must be > 0")

        window_regression_rate = window_regressions[window] / samples
        if window_regression_rate > args.max_window_regression_rate:
            fail(
                f"window={window} regression_rate={window_regression_rate} > "
                f"max_window_regression_rate={args.max_window_regression_rate}"
            )

        window_total = window_queue_budget_total[window]
        if window_total <= 0:
            fail(f"window={window} queue_budget_total={window_total} must be > 0")

        window_budget_usage_ratio = window_queue_budget_used[window] / window_total
        if window_budget_usage_ratio > args.max_window_budget_usage_ratio:
            fail(
                f"window={window} budget_usage_ratio={window_budget_usage_ratio} > "
                f"max_window_budget_usage_ratio={args.max_window_budget_usage_ratio}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
