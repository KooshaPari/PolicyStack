#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E170 [lane B] scheduler regression stability gate failed: {message}",
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
    parser.add_argument("--regressions-key", default="regressions")
    parser.add_argument("--stability-score-key", default="stability_score")
    parser.add_argument("--queue-depth-key", default="queue_depth")
    parser.add_argument("--queue-jitter-key", default="queue_jitter")
    parser.add_argument("--instability-events-key", default="instability_events")
    parser.add_argument("--min-total-samples", type=float, default=1.0)
    parser.add_argument("--max-total-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-window-regression-rate", type=float, default=0.0)
    parser.add_argument("--min-average-stability", type=float, default=0.0)
    parser.add_argument("--min-window-average-stability", type=float, default=0.0)
    parser.add_argument("--max-average-queue-depth", type=float, default=0.0)
    parser.add_argument("--max-window-average-queue-depth", type=float, default=0.0)
    parser.add_argument("--max-queue-depth", type=float, default=0.0)
    parser.add_argument("--max-total-queue-jitter", type=float, default=0.0)
    parser.add_argument("--max-total-instability-rate", type=float, default=0.0)
    parser.add_argument("--max-window-instability-rate", type=float, default=0.0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_samples = 0.0
    total_regressions = 0
    weighted_stability_sum = 0.0
    total_queue_depth = 0.0
    max_queue_depth = 0.0
    total_queue_jitter = 0.0
    total_instability_events = 0
    window_samples: dict[str, float] = {}
    window_regressions: dict[str, int] = {}
    window_weighted_stability: dict[str, float] = {}
    window_queue_depth_totals: dict[str, float] = {}
    window_queue_depth_max: dict[str, float] = {}
    window_queue_jitter: dict[str, float] = {}

    for row in records:
        samples = parse_float(row.get(args.samples_key), args.samples_key)
        regressions = parse_int(row.get(args.regressions_key, 0), args.regressions_key)
        stability_score = parse_float(row.get(args.stability_score_key), args.stability_score_key)
        queue_depth = parse_float(row.get(args.queue_depth_key, 0), args.queue_depth_key)
        queue_jitter = parse_float(row.get(args.queue_jitter_key, 0), args.queue_jitter_key)
        instability_events = parse_int(
            row.get(args.instability_events_key, 0),
            args.instability_events_key,
        )

        if samples < 0:
            fail(f"samples for {args.samples_key} must be >= 0; got {samples}")
        if regressions < 0:
            fail(f"regressions for {args.regressions_key} must be >= 0; got {regressions}")
        if stability_score < 0 or stability_score > 1:
            fail(
                f"stability_score for {args.stability_score_key} must be within [0, 1]; got "
                f"{stability_score}"
            )
        if queue_depth < 0:
            fail(f"queue_depth for {args.queue_depth_key} must be >= 0; got {queue_depth}")
        if queue_jitter < 0:
            fail(f"queue_jitter for {args.queue_jitter_key} must be >= 0; got {queue_jitter}")
        if instability_events < 0:
            fail(
                f"instability_events for {args.instability_events_key} must be >= 0; got "
                f"{instability_events}"
            )
        if regressions > samples:
            fail(f"regressions={regressions} cannot exceed samples={samples}")
        if instability_events > samples:
            fail(
                f"instability_events={instability_events} cannot exceed "
                f"samples={samples}"
            )

        total_samples += samples
        total_regressions += regressions
        weighted_stability_sum += stability_score * samples
        total_queue_depth += queue_depth
        max_queue_depth = max(max_queue_depth, queue_depth)
        total_queue_jitter += queue_jitter
        total_instability_events += instability_events

        window = str(row.get(args.window_key, "default"))
        window_samples[window] = window_samples.get(window, 0.0) + samples
        window_regressions[window] = window_regressions.get(window, 0) + regressions
        window_weighted_stability[window] = (
            window_weighted_stability.get(window, 0.0) + (stability_score * samples)
        )
        window_queue_depth_totals[window] = (
            window_queue_depth_totals.get(window, 0.0) + queue_depth
        )
        window_queue_depth_max[window] = max(window_queue_depth_max.get(window, 0.0), queue_depth)
        window_queue_jitter[window] = window_queue_jitter.get(window, 0.0) + queue_jitter

    if total_samples < args.min_total_samples:
        fail(f"total_samples={total_samples} < min_total_samples={args.min_total_samples}")

    total_regression_rate = total_regressions / total_samples
    if total_regression_rate > args.max_total_regression_rate:
        fail(
            f"total_regression_rate={total_regression_rate} > "
            f"max_total_regression_rate={args.max_total_regression_rate}"
        )

    average_stability = weighted_stability_sum / total_samples
    if average_stability < args.min_average_stability:
        fail(
            f"average_stability={average_stability} < min_average_stability="
            f"{args.min_average_stability}"
        )

    average_queue_depth = total_queue_depth / len(records)
    if average_queue_depth > args.max_average_queue_depth:
        fail(
            f"average_queue_depth={average_queue_depth} > "
            f"max_average_queue_depth={args.max_average_queue_depth}"
        )

    if max_queue_depth > args.max_queue_depth:
        fail(f"max_queue_depth={max_queue_depth} > max_queue_depth={args.max_queue_depth}")

    if total_queue_jitter > args.max_total_queue_jitter:
        fail(
            f"total_queue_jitter={total_queue_jitter} > "
            f"max_total_queue_jitter={args.max_total_queue_jitter}"
        )

    total_instability_rate = total_instability_events / total_samples
    if total_instability_rate > args.max_total_instability_rate:
        fail(
            f"total_instability_rate={total_instability_rate} > "
            f"max_total_instability_rate={args.max_total_instability_rate}"
        )

    for window in sorted(window_samples):
        samples = window_samples[window]
        if samples <= 0:
            fail(f"window={window} samples={samples} must be > 0")

        regression_rate = window_regressions[window] / samples
        if regression_rate > args.max_window_regression_rate:
            fail(
                f"window={window} regression_rate={regression_rate} > "
                f"max_window_regression_rate={args.max_window_regression_rate}"
            )

        window_stability = window_weighted_stability[window] / samples
        if window_stability < args.min_window_average_stability:
            fail(
                f"window={window} average_stability={window_stability} < "
                f"min_window_average_stability={args.min_window_average_stability}"
            )

        window_avg_depth = window_queue_depth_totals[window] / samples
        if window_avg_depth > args.max_window_average_queue_depth:
            fail(
                f"window={window} average_queue_depth={window_avg_depth} > "
                f"max_window_average_queue_depth={args.max_window_average_queue_depth}"
            )

        window_instability_rate = (window_regressions[window] if window_regressions[window] else 0) / samples
        if window_instability_rate > args.max_window_instability_rate:
            fail(
                f"window={window} instability_rate={window_instability_rate} > "
                f"max_window_instability_rate={args.max_window_instability_rate}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
