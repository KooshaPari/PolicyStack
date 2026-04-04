#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E149 [lane B] signature preflight stability budget gate failed: {message}",
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
    parser.add_argument("--instability-events-key", default="instability_events")
    parser.add_argument("--budget-used-key", default="budget_used")
    parser.add_argument("--budget-total-key", default="budget_total")
    parser.add_argument("--stability-breach-flag-key", default="stability_breach")
    parser.add_argument("--min-total-samples", type=float, default=1.0)
    parser.add_argument("--min-average-stability", type=float, default=0.0)
    parser.add_argument("--min-window-average-stability", type=float, default=0.0)
    parser.add_argument("--max-total-instability-rate", type=float, default=0.0)
    parser.add_argument("--max-window-instability-rate", type=float, default=0.0)
    parser.add_argument("--max-total-variance", type=float, default=0.0)
    parser.add_argument("--max-total-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-window-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-stability-breach-count", type=int, default=0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_samples = 0.0
    weighted_stability_sum = 0.0
    total_variance = 0.0
    total_instability_events = 0
    total_budget_used = 0.0
    total_budget_total = 0.0
    stability_breach_count = 0
    window_samples: dict[str, float] = {}
    window_weighted_stability: dict[str, float] = {}
    window_instability_events: dict[str, int] = {}
    window_budget_used: dict[str, float] = {}
    window_budget_total: dict[str, float] = {}

    for row in records:
        samples = parse_float(row.get(args.samples_key), args.samples_key)
        stability_score = parse_float(row.get(args.stability_score_key), args.stability_score_key)
        variance = parse_float(row.get(args.variance_key, 0), args.variance_key)
        instability_events = parse_int(
            row.get(args.instability_events_key, 0),
            args.instability_events_key,
        )
        budget_used = parse_float(row.get(args.budget_used_key), args.budget_used_key)
        budget_total = parse_float(row.get(args.budget_total_key), args.budget_total_key)
        stability_breach = parse_int(row.get(args.stability_breach_flag_key, 0), args.stability_breach_flag_key)

        if samples < 0:
            fail(f"samples for {args.samples_key} must be >= 0; got {samples}")
        if stability_score < 0 or stability_score > 1:
            fail(
                f"stability_score for {args.stability_score_key} must be within [0, 1]; got "
                f"{stability_score}"
            )
        if variance < 0:
            fail(f"variance for {args.variance_key} must be >= 0; got {variance}")
        if instability_events < 0:
            fail(
                f"instability_events for {args.instability_events_key} must be >= 0; "
                f"got {instability_events}"
            )
        if instability_events > samples:
            fail(
                f"instability_events={instability_events} cannot exceed "
                f"samples={samples}"
            )
        if budget_used < 0:
            fail(f"budget_used for {args.budget_used_key} must be >= 0; got {budget_used}")
        if budget_total <= 0:
            fail(f"budget_total for {args.budget_total_key} must be > 0; got {budget_total}")
        if budget_used > budget_total:
            fail(f"budget_used={budget_used} cannot exceed budget_total={budget_total}")
        if stability_breach < 0:
            fail(
                f"stability_breach for {args.stability_breach_flag_key} must be >= 0; got "
                f"{stability_breach}"
            )

        total_samples += samples
        weighted_stability_sum += stability_score * samples
        total_variance += variance
        total_instability_events += instability_events
        total_budget_used += budget_used
        total_budget_total += budget_total
        stability_breach_count += 1 if stability_breach else 0

        window = str(row.get(args.window_key, "default"))
        window_samples[window] = window_samples.get(window, 0.0) + samples
        window_weighted_stability[window] = (
            window_weighted_stability.get(window, 0.0) + (stability_score * samples)
        )
        window_instability_events[window] = (
            window_instability_events.get(window, 0) + instability_events
        )
        window_budget_used[window] = window_budget_used.get(window, 0.0) + budget_used
        window_budget_total[window] = window_budget_total.get(window, 0.0) + budget_total

    if total_samples < args.min_total_samples:
        fail(f"total_samples={total_samples} < min_total_samples={args.min_total_samples}")

    if total_budget_total <= 0:
        fail(f"total_budget_total={total_budget_total} must be > 0")

    average_stability = weighted_stability_sum / total_samples
    if average_stability < args.min_average_stability:
        fail(
            f"average_stability={average_stability} < min_average_stability="
            f"{args.min_average_stability}"
        )

    if total_variance > args.max_total_variance:
        fail(f"total_variance={total_variance} > max_total_variance={args.max_total_variance}")

    total_instability_rate = total_instability_events / total_samples
    if total_instability_rate > args.max_total_instability_rate:
        fail(
            f"total_instability_rate={total_instability_rate} > "
            f"max_total_instability_rate={args.max_total_instability_rate}"
        )

    total_budget_usage_ratio = total_budget_used / total_budget_total
    if total_budget_usage_ratio > args.max_total_budget_usage_ratio:
        fail(
            f"total_budget_usage_ratio={total_budget_usage_ratio} > "
            f"max_total_budget_usage_ratio={args.max_total_budget_usage_ratio}"
        )

    if stability_breach_count > args.max_stability_breach_count:
        fail(
            f"stability_breach_count={stability_breach_count} > "
            f"max_stability_breach_count={args.max_stability_breach_count}"
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

        window_instability_rate = window_instability_events[window] / samples
        if window_instability_rate > args.max_window_instability_rate:
            fail(
                f"window={window} instability_rate={window_instability_rate} > "
                f"max_window_instability_rate={args.max_window_instability_rate}"
            )

        window_total = window_budget_total[window]
        if window_total <= 0:
            fail(f"window={window} budget_total={window_total} must be > 0")
        window_budget_usage_ratio = window_budget_used[window] / window_total
        if window_budget_usage_ratio > args.max_window_budget_usage_ratio:
            fail(
                f"window={window} budget_usage_ratio={window_budget_usage_ratio} > "
                f"max_window_budget_usage_ratio={args.max_window_budget_usage_ratio}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
