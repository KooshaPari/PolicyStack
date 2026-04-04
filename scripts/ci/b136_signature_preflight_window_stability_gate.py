#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E136 [lane B] signature preflight window stability gate failed: {message}",
        file=sys.stderr,
    )
    raise SystemExit(2)


def parse_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid numeric value for {field}: {value!r}")


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
    parser.add_argument("--success-rate-key", default="success_rate")
    parser.add_argument("--p95-latency-ms-key", default="p95_latency_ms")
    parser.add_argument("--drift-score-key", default="drift_score")
    parser.add_argument("--min-total-samples", type=float, default=1.0)
    parser.add_argument("--min-average-success-rate", type=float, default=0.0)
    parser.add_argument("--min-window-average-success-rate", type=float, default=0.0)
    parser.add_argument("--max-p95-latency-ms", type=float, default=0.0)
    parser.add_argument("--max-window-average-drift-score", type=float, default=0.0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_samples = 0.0
    weighted_success_sum = 0.0
    max_p95_latency = 0.0
    window_samples: dict[str, float] = {}
    window_weighted_success: dict[str, float] = {}
    window_drift_totals: dict[str, float] = {}
    window_counts: dict[str, int] = {}

    for row in records:
        samples = parse_float(row.get(args.samples_key), args.samples_key)
        success_rate = parse_float(row.get(args.success_rate_key), args.success_rate_key)
        p95_latency_ms = parse_float(
            row.get(args.p95_latency_ms_key, 0),
            args.p95_latency_ms_key,
        )
        drift_score = parse_float(row.get(args.drift_score_key, 0), args.drift_score_key)

        if samples < 0:
            fail(f"samples for {args.samples_key} must be >= 0; got {samples}")
        if success_rate < 0 or success_rate > 1:
            fail(f"success_rate for {args.success_rate_key} must be within [0, 1]; got {success_rate}")
        if p95_latency_ms < 0:
            fail(f"p95_latency_ms for {args.p95_latency_ms_key} must be >= 0; got {p95_latency_ms}")
        if drift_score < 0:
            fail(f"drift_score for {args.drift_score_key} must be >= 0; got {drift_score}")

        total_samples += samples
        weighted_success_sum += success_rate * samples
        max_p95_latency = max(max_p95_latency, p95_latency_ms)

        window = str(row.get(args.window_key, "default"))
        window_samples[window] = window_samples.get(window, 0.0) + samples
        window_weighted_success[window] = window_weighted_success.get(window, 0.0) + (
            success_rate * samples
        )
        window_drift_totals[window] = window_drift_totals.get(window, 0.0) + drift_score
        window_counts[window] = window_counts.get(window, 0) + 1

    if total_samples < args.min_total_samples:
        fail(f"total_samples={total_samples} < min_total_samples={args.min_total_samples}")

    average_success_rate = weighted_success_sum / total_samples
    if average_success_rate < args.min_average_success_rate:
        fail(
            f"average_success_rate={average_success_rate} < min_average_success_rate="
            f"{args.min_average_success_rate}"
        )

    if max_p95_latency > args.max_p95_latency_ms:
        fail(f"max_p95_latency_ms={max_p95_latency} > max_p95_latency_ms={args.max_p95_latency_ms}")

    for window in sorted(window_samples):
        samples = window_samples[window]
        if samples <= 0:
            fail(f"window={window} samples={samples} must be > 0")
        window_avg_success = window_weighted_success[window] / samples
        if window_avg_success < args.min_window_average_success_rate:
            fail(
                f"window={window} average_success_rate={window_avg_success} < "
                f"min_window_average_success_rate={args.min_window_average_success_rate}"
            )

        window_avg_drift = window_drift_totals[window] / window_counts[window]
        if window_avg_drift > args.max_window_average_drift_score:
            fail(
                f"window={window} average_drift_score={window_avg_drift} > "
                f"max_window_average_drift_score={args.max_window_average_drift_score}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
