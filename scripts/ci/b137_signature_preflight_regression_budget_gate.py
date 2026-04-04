#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E137 [lane B] signature preflight regression budget gate failed: {message}",
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
    parser.add_argument("--critical-regressions-key", default="critical_regressions")
    parser.add_argument("--budget-used-key", default="budget_used")
    parser.add_argument("--budget-total-key", default="budget_total")
    parser.add_argument("--retry-count-key", default="retry_count")
    parser.add_argument("--min-total-samples", type=float, default=1.0)
    parser.add_argument("--max-total-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-window-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-total-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-window-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-total-critical-regressions", type=int, default=0)
    parser.add_argument("--max-total-retry-count", type=int, default=0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_samples = 0.0
    total_regressions = 0
    total_critical_regressions = 0
    total_budget_used = 0.0
    total_budget_total = 0.0
    total_retry_count = 0
    window_samples: dict[str, float] = {}
    window_regressions: dict[str, int] = {}
    window_budget_used: dict[str, float] = {}
    window_budget_total: dict[str, float] = {}

    for row in records:
        samples = parse_float(row.get(args.samples_key), args.samples_key)
        regressions = parse_int(row.get(args.regressions_key, 0), args.regressions_key)
        critical_regressions = parse_int(
            row.get(args.critical_regressions_key, 0),
            args.critical_regressions_key,
        )
        budget_used = parse_float(row.get(args.budget_used_key), args.budget_used_key)
        budget_total = parse_float(row.get(args.budget_total_key), args.budget_total_key)
        retry_count = parse_int(row.get(args.retry_count_key, 0), args.retry_count_key)

        if samples < 0:
            fail(f"samples for {args.samples_key} must be >= 0; got {samples}")
        if regressions < 0:
            fail(f"regressions for {args.regressions_key} must be >= 0; got {regressions}")
        if critical_regressions < 0:
            fail(
                f"critical regressions for {args.critical_regressions_key} must be >= 0; got "
                f"{critical_regressions}"
            )
        if regressions > samples:
            fail(f"regressions={regressions} cannot exceed samples={samples}")
        if critical_regressions > regressions:
            fail(
                f"critical_regressions={critical_regressions} cannot exceed regressions={regressions}"
            )
        if budget_used < 0:
            fail(f"budget_used for {args.budget_used_key} must be >= 0; got {budget_used}")
        if budget_total <= 0:
            fail(f"budget_total for {args.budget_total_key} must be > 0; got {budget_total}")
        if budget_used > budget_total:
            fail(f"budget_used={budget_used} cannot exceed budget_total={budget_total}")
        if retry_count < 0:
            fail(f"retry_count for {args.retry_count_key} must be >= 0; got {retry_count}")

        total_samples += samples
        total_regressions += regressions
        total_critical_regressions += critical_regressions
        total_budget_used += budget_used
        total_budget_total += budget_total
        total_retry_count += retry_count

        window = str(row.get(args.window_key, "default"))
        window_samples[window] = window_samples.get(window, 0.0) + samples
        window_regressions[window] = window_regressions.get(window, 0) + regressions
        window_budget_used[window] = window_budget_used.get(window, 0.0) + budget_used
        window_budget_total[window] = window_budget_total.get(window, 0.0) + budget_total

    if total_samples < args.min_total_samples:
        fail(f"total_samples={total_samples} < min_total_samples={args.min_total_samples}")

    if total_budget_total <= 0:
        fail(f"total_budget_total={total_budget_total} must be > 0")

    total_regression_rate = total_regressions / total_samples
    if total_regression_rate > args.max_total_regression_rate:
        fail(
            f"total_regression_rate={total_regression_rate} > max_total_regression_rate="
            f"{args.max_total_regression_rate}"
        )

    total_budget_usage_ratio = total_budget_used / total_budget_total
    if total_budget_usage_ratio > args.max_total_budget_usage_ratio:
        fail(
            f"total_budget_usage_ratio={total_budget_usage_ratio} > "
            f"max_total_budget_usage_ratio={args.max_total_budget_usage_ratio}"
        )

    if total_critical_regressions > args.max_total_critical_regressions:
        fail(
            f"total_critical_regressions={total_critical_regressions} > "
            f"max_total_critical_regressions={args.max_total_critical_regressions}"
        )

    if total_retry_count > args.max_total_retry_count:
        fail(
            f"total_retry_count={total_retry_count} > "
            f"max_total_retry_count={args.max_total_retry_count}"
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
