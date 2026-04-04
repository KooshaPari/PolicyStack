#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E247 [lane B] signature entropy budget gate failed: {message}",
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
    parser.add_argument("--entropy-score-key", default="entropy_score")
    parser.add_argument("--entropy-regressions-key", default="entropy_regressions")
    parser.add_argument("--invalid-signature-events-key", default="invalid_signature_events")
    parser.add_argument("--budget-used-key", default="budget_used")
    parser.add_argument("--budget-total-key", default="budget_total")
    parser.add_argument("--min-total-samples", type=float, default=1.0)
    parser.add_argument("--min-average-entropy-score", type=float, default=0.0)
    parser.add_argument("--min-window-average-entropy-score", type=float, default=0.0)
    parser.add_argument("--max-total-entropy-regressions", type=int, default=0)
    parser.add_argument("--max-window-entropy-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-total-invalid-signature-events", type=int, default=0)
    parser.add_argument("--max-total-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-window-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-total-variance", type=float, default=0.0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_samples = 0.0
    weighted_entropy_sum = 0.0
    total_entropy_regressions = 0
    total_invalid_signature_events = 0
    total_budget_used = 0.0
    total_budget_total = 0.0
    total_variance = 0.0
    window_samples: dict[str, float] = {}
    window_weighted_entropy: dict[str, float] = {}
    window_entropy_regressions: dict[str, int] = {}
    window_budget_used: dict[str, float] = {}
    window_budget_total: dict[str, float] = {}

    for row in records:
        samples = parse_float(row.get(args.samples_key), args.samples_key)
        entropy_score = parse_float(row.get(args.entropy_score_key), args.entropy_score_key)
        entropy_regressions = parse_int(
            row.get(args.entropy_regressions_key, 0),
            args.entropy_regressions_key,
        )
        invalid_signature_events = parse_int(
            row.get(args.invalid_signature_events_key, 0),
            args.invalid_signature_events_key,
        )
        budget_used = parse_float(row.get(args.budget_used_key), args.budget_used_key)
        budget_total = parse_float(row.get(args.budget_total_key), args.budget_total_key)

        if samples < 0:
            fail(f"samples for {args.samples_key} must be >= 0; got {samples}")
        if entropy_score < 0 or entropy_score > 1:
            fail(
                f"entropy_score for {args.entropy_score_key} must be within [0, 1]; got "
                f"{entropy_score}"
            )
        if entropy_regressions < 0:
            fail(
                f"entropy_regressions for {args.entropy_regressions_key} must be >= 0; got "
                f"{entropy_regressions}"
            )
        if invalid_signature_events < 0:
            fail(
                f"invalid_signature_events for {args.invalid_signature_events_key} must be >= 0; "
                f"got {invalid_signature_events}"
            )
        if entropy_regressions > samples:
            fail(f"entropy_regressions={entropy_regressions} cannot exceed samples={samples}")
        if budget_used < 0:
            fail(f"budget_used for {args.budget_used_key} must be >= 0; got {budget_used}")
        if budget_total <= 0:
            fail(f"budget_total for {args.budget_total_key} must be > 0; got {budget_total}")
        if budget_used > budget_total:
            fail(f"budget_used={budget_used} cannot exceed budget_total={budget_total}")

        total_samples += samples
        weighted_entropy_sum += entropy_score * samples
        total_entropy_regressions += entropy_regressions
        total_invalid_signature_events += invalid_signature_events
        total_budget_used += budget_used
        total_budget_total += budget_total

        window = str(row.get(args.window_key, "default"))
        window_samples[window] = window_samples.get(window, 0.0) + samples
        window_weighted_entropy[window] = window_weighted_entropy.get(window, 0.0) + (
            entropy_score * samples
        )
        window_entropy_regressions[window] = (
            window_entropy_regressions.get(window, 0) + entropy_regressions
        )
        window_budget_used[window] = window_budget_used.get(window, 0.0) + budget_used
        window_budget_total[window] = window_budget_total.get(window, 0.0) + budget_total

    if total_samples < args.min_total_samples:
        fail(f"total_samples={total_samples} < min_total_samples={args.min_total_samples}")

    if total_budget_total <= 0:
        fail(f"total_budget_total={total_budget_total} must be > 0")

    average_entropy_score = weighted_entropy_sum / total_samples
    if average_entropy_score < args.min_average_entropy_score:
        fail(
            f"average_entropy_score={average_entropy_score} < min_average_entropy_score="
            f"{args.min_average_entropy_score}"
        )

    total_entropy_regression_rate = total_entropy_regressions / total_samples
    if total_entropy_regression_rate > args.max_window_entropy_regression_rate:
        fail(
            f"total_entropy_regression_rate={total_entropy_regression_rate} > "
            f"max_window_entropy_regression_rate={args.max_window_entropy_regression_rate}"
        )

    if total_entropy_regressions > args.max_total_entropy_regressions:
        fail(
            f"total_entropy_regressions={total_entropy_regressions} > "
            f"max_total_entropy_regressions={args.max_total_entropy_regressions}"
        )

    if total_invalid_signature_events > args.max_total_invalid_signature_events:
        fail(
            f"total_invalid_signature_events={total_invalid_signature_events} > "
            f"max_total_invalid_signature_events={args.max_total_invalid_signature_events}"
        )

    total_budget_usage_ratio = total_budget_used / total_budget_total
    if total_budget_usage_ratio > args.max_total_budget_usage_ratio:
        fail(
            f"total_budget_usage_ratio={total_budget_usage_ratio} > "
            f"max_total_budget_usage_ratio={args.max_total_budget_usage_ratio}"
        )

    if total_variance > args.max_total_variance:
        fail(f"total_variance={total_variance} > max_total_variance={args.max_total_variance}")

    for window in sorted(window_samples):
        samples = window_samples[window]
        if samples <= 0:
            fail(f"window={window} samples={samples} must be > 0")

        window_average_entropy = window_weighted_entropy[window] / samples
        if window_average_entropy < args.min_window_average_entropy_score:
            fail(
                f"window={window} average_entropy_score={window_average_entropy} < "
                f"min_window_average_entropy_score={args.min_window_average_entropy_score}"
            )

        window_entropy_regression_rate = window_entropy_regressions[window] / samples
        if window_entropy_regression_rate > args.max_window_entropy_regression_rate:
            fail(
                f"window={window} entropy_regression_rate={window_entropy_regression_rate} > "
                f"max_window_entropy_regression_rate={args.max_window_entropy_regression_rate}"
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
