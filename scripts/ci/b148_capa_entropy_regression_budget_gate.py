#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E148 [lane B] capa entropy regression budget gate failed: {message}",
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
    parser.add_argument("--operations-key", default="operations")
    parser.add_argument("--entropy-score-key", default="entropy_score")
    parser.add_argument("--entropy-regressions-key", default="entropy_regressions")
    parser.add_argument("--invalid-entropy-events-key", default="invalid_entropy_events")
    parser.add_argument("--capa-failures-key", default="capa_failures")
    parser.add_argument("--budget-used-key", default="budget_used")
    parser.add_argument("--budget-total-key", default="budget_total")
    parser.add_argument("--min-total-operations", type=float, default=1.0)
    parser.add_argument("--min-average-entropy-score", type=float, default=0.0)
    parser.add_argument("--min-window-average-entropy-score", type=float, default=0.0)
    parser.add_argument("--max-total-entropy-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-total-entropy-regressions", type=int, default=0)
    parser.add_argument("--max-window-entropy-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-total-invalid-entropy-events", type=int, default=0)
    parser.add_argument("--max-total-capa-failures", type=int, default=0)
    parser.add_argument("--max-total-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-window-budget-usage-ratio", type=float, default=0.0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_operations = 0.0
    weighted_entropy_sum = 0.0
    total_entropy_regressions = 0
    total_invalid_entropy_events = 0
    total_capa_failures = 0
    total_budget_used = 0.0
    total_budget_total = 0.0
    window_operations: dict[str, float] = {}
    window_weighted_entropy: dict[str, float] = {}
    window_entropy_regressions: dict[str, int] = {}
    window_budget_used: dict[str, float] = {}
    window_budget_total: dict[str, float] = {}

    for row in records:
        operations = parse_float(row.get(args.operations_key), args.operations_key)
        entropy_score = parse_float(row.get(args.entropy_score_key), args.entropy_score_key)
        entropy_regressions = parse_int(
            row.get(args.entropy_regressions_key, 0),
            args.entropy_regressions_key,
        )
        invalid_entropy_events = parse_int(
            row.get(args.invalid_entropy_events_key, 0),
            args.invalid_entropy_events_key,
        )
        capa_failures = parse_int(row.get(args.capa_failures_key, 0), args.capa_failures_key)
        budget_used = parse_float(row.get(args.budget_used_key), args.budget_used_key)
        budget_total = parse_float(row.get(args.budget_total_key), args.budget_total_key)

        if operations < 0:
            fail(f"operations for {args.operations_key} must be >= 0; got {operations}")
        if entropy_score < 0 or entropy_score > 1:
            fail(
                f"entropy_score for {args.entropy_score_key} must be within [0, 1]; got "
                f"{entropy_score}"
            )
        if entropy_regressions < 0:
            fail(
                f"entropy_regressions for {args.entropy_regressions_key} must be >= 0; "
                f"got {entropy_regressions}"
            )
        if entropy_regressions > operations:
            fail(f"entropy_regressions={entropy_regressions} cannot exceed operations={operations}")
        if invalid_entropy_events < 0:
            fail(
                f"invalid_entropy_events for {args.invalid_entropy_events_key} must be >= 0; "
                f"got {invalid_entropy_events}"
            )
        if capa_failures < 0:
            fail(
                f"capa_failures for {args.capa_failures_key} must be >= 0; got {capa_failures}"
            )
        if capa_failures > operations:
            fail(f"capa_failures={capa_failures} cannot exceed operations={operations}")
        if budget_used < 0:
            fail(f"budget_used for {args.budget_used_key} must be >= 0; got {budget_used}")
        if budget_total <= 0:
            fail(f"budget_total for {args.budget_total_key} must be > 0; got {budget_total}")
        if budget_used > budget_total:
            fail(f"budget_used={budget_used} cannot exceed budget_total={budget_total}")

        total_operations += operations
        weighted_entropy_sum += entropy_score * operations
        total_entropy_regressions += entropy_regressions
        total_invalid_entropy_events += invalid_entropy_events
        total_capa_failures += capa_failures
        total_budget_used += budget_used
        total_budget_total += budget_total

        window = str(row.get(args.window_key, "default"))
        window_operations[window] = window_operations.get(window, 0.0) + operations
        window_weighted_entropy[window] = (
            window_weighted_entropy.get(window, 0.0) + (entropy_score * operations)
        )
        window_entropy_regressions[window] = (
            window_entropy_regressions.get(window, 0) + entropy_regressions
        )
        window_budget_used[window] = window_budget_used.get(window, 0.0) + budget_used
        window_budget_total[window] = window_budget_total.get(window, 0.0) + budget_total

    if total_operations < args.min_total_operations:
        fail(f"total_operations={total_operations} < min_total_operations={args.min_total_operations}")

    if total_budget_total <= 0:
        fail(f"total_budget_total={total_budget_total} must be > 0")

    average_entropy_score = weighted_entropy_sum / total_operations
    if average_entropy_score < args.min_average_entropy_score:
        fail(
            f"average_entropy_score={average_entropy_score} < min_average_entropy_score="
            f"{args.min_average_entropy_score}"
        )

    total_entropy_regression_rate = total_entropy_regressions / total_operations
    if total_entropy_regression_rate > args.max_total_entropy_regression_rate:
        fail(
            f"total_entropy_regression_rate={total_entropy_regression_rate} > "
            f"max_entropy_regression_rate={args.max_total_entropy_regression_rate}"
        )

    if total_entropy_regressions > args.max_total_entropy_regressions:
        fail(
            f"total_entropy_regressions={total_entropy_regressions} > "
            f"max_total_entropy_regressions={args.max_total_entropy_regressions}"
        )

    if total_invalid_entropy_events > args.max_total_invalid_entropy_events:
        fail(
            f"total_invalid_entropy_events={total_invalid_entropy_events} > "
            f"max_total_invalid_entropy_events={args.max_total_invalid_entropy_events}"
        )

    if total_capa_failures > args.max_total_capa_failures:
        fail(
            f"total_capa_failures={total_capa_failures} > "
            f"max_total_capa_failures={args.max_total_capa_failures}"
        )

    total_budget_usage_ratio = total_budget_used / total_budget_total
    if total_budget_usage_ratio > args.max_total_budget_usage_ratio:
        fail(
            f"total_budget_usage_ratio={total_budget_usage_ratio} > "
            f"max_total_budget_usage_ratio={args.max_total_budget_usage_ratio}"
        )

    for window in sorted(window_operations):
        operations = window_operations[window]
        if operations <= 0:
            fail(f"window={window} operations={operations} must be > 0")

        window_average_entropy = window_weighted_entropy[window] / operations
        if window_average_entropy < args.min_window_average_entropy_score:
            fail(
                f"window={window} average_entropy_score={window_average_entropy} < "
                f"min_window_average_entropy_score={args.min_window_average_entropy_score}"
            )

        window_entropy_regression_rate = window_entropy_regressions[window] / operations
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
