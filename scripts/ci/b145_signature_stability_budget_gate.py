#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E145 [lane B] signature stability budget gate failed: {message}",
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
    parser.add_argument("--stability-score-key", default="stability_score")
    parser.add_argument("--variance-key", default="variance")
    parser.add_argument("--unstable-events-key", default="unstable_events")
    parser.add_argument("--budget-used-key", default="budget_used")
    parser.add_argument("--budget-total-key", default="budget_total")
    parser.add_argument("--budget-breach-flag-key", default="budget_breached")
    parser.add_argument("--min-total-samples", type=float, default=1.0)
    parser.add_argument("--min-average-stability", type=float, default=0.0)
    parser.add_argument("--min-window-average-stability", type=float, default=0.0)
    parser.add_argument("--max-total-unstable-rate", type=float, default=0.0)
    parser.add_argument("--max-window-unstable-rate", type=float, default=0.0)
    parser.add_argument("--max-total-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-window-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-budget-breach-count", type=int, default=0)
    parser.add_argument("--max-total-variance", type=float, default=0.0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_samples = 0.0
    weighted_stability_sum = 0.0
    variance_total = 0.0
    total_unstable_events = 0.0
    total_budget_used = 0.0
    total_budget_total = 0.0
    budget_breach_count = 0
    window_samples: dict[str, float] = {}
    window_weighted_stability: dict[str, float] = {}
    window_unstable_events: dict[str, float] = {}
    window_budget_used: dict[str, float] = {}
    window_budget_total: dict[str, float] = {}

    for row in records:
        samples = parse_float(row.get(args.samples_key), args.samples_key)
        stability_score = parse_float(
            row.get(args.stability_score_key),
            args.stability_score_key,
        )
        variance = parse_float(row.get(args.variance_key, 0), args.variance_key)
        unstable_events = parse_float(
            row.get(args.unstable_events_key, 0),
            args.unstable_events_key,
        )
        budget_used = parse_float(row.get(args.budget_used_key), args.budget_used_key)
        budget_total = parse_float(row.get(args.budget_total_key), args.budget_total_key)
        budget_breached = parse_int(
            row.get(args.budget_breach_flag_key, 0),
            args.budget_breach_flag_key,
        )

        if samples < 0:
            fail(f"samples for {args.samples_key} must be >= 0; got {samples}")
        if stability_score < 0 or stability_score > 1:
            fail(
                f"stability_score for {args.stability_score_key} must be within [0, 1]; got "
                f"{stability_score}"
            )
        if variance < 0:
            fail(f"variance for {args.variance_key} must be >= 0; got {variance}")
        if unstable_events < 0:
            fail(
                f"unstable_events for {args.unstable_events_key} must be >= 0; "
                f"got {unstable_events}"
            )
        if budget_used < 0:
            fail(f"budget_used for {args.budget_used_key} must be >= 0; got {budget_used}")
        if budget_total <= 0:
            fail(f"budget_total for {args.budget_total_key} must be > 0; got {budget_total}")
        if budget_used > budget_total:
            fail(f"budget_used={budget_used} cannot exceed budget_total={budget_total}")
        if budget_breached < 0:
            fail(
                f"budget_breached for {args.budget_breach_flag_key} must be >= 0; "
                f"got {budget_breached}"
            )

        total_samples += samples
        weighted_stability_sum += stability_score * samples
        variance_total += variance
        total_unstable_events += unstable_events
        total_budget_used += budget_used
        total_budget_total += budget_total
        budget_breach_count += 1 if budget_breached else 0

        window = str(row.get(args.window_key, "default"))
        window_samples[window] = window_samples.get(window, 0.0) + samples
        window_weighted_stability[window] = (
            window_weighted_stability.get(window, 0.0) + (stability_score * samples)
        )
        window_unstable_events[window] = (
            window_unstable_events.get(window, 0.0) + unstable_events
        )
        window_budget_used[window] = window_budget_used.get(window, 0.0) + budget_used
        window_budget_total[window] = window_budget_total.get(window, 0.0) + budget_total

    if total_samples < args.min_total_samples:
        fail(f"total_samples={total_samples} < min_total_samples={args.min_total_samples}")

    if variance_total > args.max_total_variance:
        fail(f"total_variance={variance_total} > max_total_variance={args.max_total_variance}")

    if total_budget_total <= 0:
        fail(f"total_budget_total={total_budget_total} must be > 0")

    average_stability = weighted_stability_sum / total_samples
    if average_stability < args.min_average_stability:
        fail(
            f"average_stability={average_stability} < min_average_stability="
            f"{args.min_average_stability}"
        )

    total_unstable_rate = total_unstable_events / total_samples
    if total_unstable_rate > args.max_total_unstable_rate:
        fail(
            f"total_unstable_rate={total_unstable_rate} > max_total_unstable_rate="
            f"{args.max_total_unstable_rate}"
        )

    total_budget_usage_ratio = total_budget_used / total_budget_total
    if total_budget_usage_ratio > args.max_total_budget_usage_ratio:
        fail(
            f"total_budget_usage_ratio={total_budget_usage_ratio} > "
            f"max_total_budget_usage_ratio={args.max_total_budget_usage_ratio}"
        )

    if budget_breach_count > args.max_budget_breach_count:
        fail(
            f"budget_breach_count={budget_breach_count} > "
            f"max_budget_breach_count={args.max_budget_breach_count}"
        )

    for window in sorted(window_samples):
        samples = window_samples[window]
        if samples <= 0:
            fail(f"window={window} samples={samples} must be > 0")

        window_stability = window_weighted_stability[window] / samples
        if window_stability < args.min_window_average_stability:
            fail(
                f"window={window} average_stability={window_stability} < "
                f"min_window_average_stability={args.min_window_average_stability}"
            )

        window_unstable_rate = window_unstable_events[window] / samples
        if window_unstable_rate > args.max_window_unstable_rate:
            fail(
                f"window={window} unstable_rate={window_unstable_rate} > "
                f"max_window_unstable_rate={args.max_window_unstable_rate}"
            )

        window_budget_total_value = window_budget_total[window]
        if window_budget_total_value <= 0:
            fail(f"window={window} budget_total={window_budget_total_value} must be > 0")
        window_budget_usage_ratio = window_budget_used[window] / window_budget_total_value
        if window_budget_usage_ratio > args.max_window_budget_usage_ratio:
            fail(
                f"window={window} budget_usage_ratio={window_budget_usage_ratio} > "
                f"max_window_budget_usage_ratio={args.max_window_budget_usage_ratio}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
