#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E146 [lane B] scheduler deadline regression budget gate failed: {message}",
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
    parser.add_argument("--deadline-regressions-key", default="deadline_regressions")
    parser.add_argument("--deadline-breach-count-key", default="deadline_breach_count")
    parser.add_argument("--deadline-overruns-key", default="deadline_overruns")
    parser.add_argument("--deadline-budget-used-key", default="deadline_budget_used")
    parser.add_argument("--deadline-budget-total-key", default="deadline_budget_total")
    parser.add_argument("--min-total-samples", type=float, default=1.0)
    parser.add_argument("--max-total-deadline-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-window-deadline-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-total-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-window-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-total-deadline-breach-count", type=int, default=0)
    parser.add_argument("--max-total-deadline-overruns", type=int, default=0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_samples = 0.0
    total_deadline_regressions = 0
    total_deadline_breach_count = 0
    total_deadline_overruns = 0
    total_budget_used = 0.0
    total_budget_total = 0.0
    window_samples: dict[str, float] = {}
    window_regressions: dict[str, int] = {}
    window_budget_used: dict[str, float] = {}
    window_budget_total: dict[str, float] = {}

    for row in records:
        samples = parse_float(row.get(args.samples_key), args.samples_key)
        deadline_regressions = parse_int(
            row.get(args.deadline_regressions_key, 0),
            args.deadline_regressions_key,
        )
        deadline_breach_count = parse_int(
            row.get(args.deadline_breach_count_key, 0),
            args.deadline_breach_count_key,
        )
        deadline_overruns = parse_int(
            row.get(args.deadline_overruns_key, 0),
            args.deadline_overruns_key,
        )
        budget_used = parse_float(
            row.get(args.deadline_budget_used_key),
            args.deadline_budget_used_key,
        )
        budget_total = parse_float(
            row.get(args.deadline_budget_total_key),
            args.deadline_budget_total_key,
        )

        if samples < 0:
            fail(f"samples for {args.samples_key} must be >= 0; got {samples}")
        if deadline_regressions < 0:
            fail(
                f"deadline_regressions for {args.deadline_regressions_key} must be >= 0; "
                f"got {deadline_regressions}"
            )
        if deadline_breach_count < 0:
            fail(
                f"deadline_breach_count for {args.deadline_breach_count_key} must be >= 0; "
                f"got {deadline_breach_count}"
            )
        if deadline_overruns < 0:
            fail(
                f"deadline_overruns for {args.deadline_overruns_key} must be >= 0; "
                f"got {deadline_overruns}"
            )
        if deadline_regressions > samples:
            fail(
                f"deadline_regressions={deadline_regressions} cannot exceed "
                f"samples={samples}"
            )
        if budget_used < 0:
            fail(f"deadline_budget_used for {args.deadline_budget_used_key} must be >= 0; got {budget_used}")
        if budget_total <= 0:
            fail(
                f"deadline_budget_total for {args.deadline_budget_total_key} must be > 0; "
                f"got {budget_total}"
            )
        if budget_used > budget_total:
            fail(
                f"deadline_budget_used={budget_used} cannot exceed "
                f"deadline_budget_total={budget_total}"
            )

        total_samples += samples
        total_deadline_regressions += deadline_regressions
        total_deadline_breach_count += deadline_breach_count
        total_deadline_overruns += deadline_overruns
        total_budget_used += budget_used
        total_budget_total += budget_total

        window = str(row.get(args.window_key, "default"))
        window_samples[window] = window_samples.get(window, 0.0) + samples
        window_regressions[window] = window_regressions.get(window, 0) + deadline_regressions
        window_budget_used[window] = window_budget_used.get(window, 0.0) + budget_used
        window_budget_total[window] = window_budget_total.get(window, 0.0) + budget_total

    if total_samples < args.min_total_samples:
        fail(f"total_samples={total_samples} < min_total_samples={args.min_total_samples}")

    if total_budget_total <= 0:
        fail(f"total_deadline_budget_total={total_budget_total} must be > 0")

    total_regression_rate = total_deadline_regressions / total_samples
    if total_regression_rate > args.max_total_deadline_regression_rate:
        fail(
            f"total_deadline_regression_rate={total_regression_rate} > "
            f"max_total_deadline_regression_rate={args.max_total_deadline_regression_rate}"
        )

    total_budget_usage_ratio = total_budget_used / total_budget_total
    if total_budget_usage_ratio > args.max_total_budget_usage_ratio:
        fail(
            f"total_budget_usage_ratio={total_budget_usage_ratio} > "
            f"max_total_budget_usage_ratio={args.max_total_budget_usage_ratio}"
        )

    if total_deadline_breach_count > args.max_total_deadline_breach_count:
        fail(
            f"total_deadline_breach_count={total_deadline_breach_count} > "
            f"max_total_deadline_breach_count={args.max_total_deadline_breach_count}"
        )

    if total_deadline_overruns > args.max_total_deadline_overruns:
        fail(
            f"total_deadline_overruns={total_deadline_overruns} > "
            f"max_total_deadline_overruns={args.max_total_deadline_overruns}"
        )

    for window in sorted(window_samples):
        samples = window_samples[window]
        if samples <= 0:
            fail(f"window={window} samples={samples} must be > 0")

        window_regression_rate = window_regressions[window] / samples
        if window_regression_rate > args.max_window_deadline_regression_rate:
            fail(
                f"window={window} deadline_regression_rate={window_regression_rate} > "
                f"max_window_deadline_regression_rate={args.max_window_deadline_regression_rate}"
            )

        window_budget_total_value = window_budget_total[window]
        if window_budget_total_value <= 0:
            fail(f"window={window} deadline_budget_total={window_budget_total_value} must be > 0")
        window_budget_usage_ratio = window_budget_used[window] / window_budget_total_value
        if window_budget_usage_ratio > args.max_window_budget_usage_ratio:
            fail(
                f"window={window} budget_usage_ratio={window_budget_usage_ratio} > "
                f"max_window_budget_usage_ratio={args.max_window_budget_usage_ratio}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

