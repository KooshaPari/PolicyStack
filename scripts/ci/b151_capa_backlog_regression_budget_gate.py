#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E151 [lane B] capa backlog regression budget gate failed: {message}",
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
    parser.add_argument("--backlog-before-key", default="backlog_before")
    parser.add_argument("--backlog-after-key", default="backlog_after")
    parser.add_argument("--backlog-regressions-key", default="backlog_regressions")
    parser.add_argument("--critical-regressions-key", default="critical_regressions")
    parser.add_argument("--backlog-overflow-events-key", default="backlog_overflow_events")
    parser.add_argument("--capa-failures-key", default="capa_failures")
    parser.add_argument("--budget-used-key", default="budget_used")
    parser.add_argument("--budget-total-key", default="budget_total")
    parser.add_argument("--min-total-operations", type=float, default=1.0)
    parser.add_argument("--max-total-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-window-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-total-critical-regressions", type=int, default=0)
    parser.add_argument("--max-total-overflow-events", type=int, default=0)
    parser.add_argument("--max-total-capa-failures", type=int, default=0)
    parser.add_argument("--max-average-backlog-growth", type=float, default=0.0)
    parser.add_argument("--max-total-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-window-budget-usage-ratio", type=float, default=0.0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_operations = 0.0
    total_backlog_regressions = 0
    total_critical_regressions = 0
    total_backlog_overflow_events = 0
    total_capa_failures = 0
    total_budget_used = 0.0
    total_budget_total = 0.0
    total_backlog_growth = 0.0
    window_operations: dict[str, float] = {}
    window_regressions: dict[str, int] = {}
    window_budget_used: dict[str, float] = {}
    window_budget_total: dict[str, float] = {}
    window_backlog_growth: dict[str, float] = {}

    for row in records:
        operations = parse_float(row.get(args.operations_key), args.operations_key)
        backlog_before = parse_float(row.get(args.backlog_before_key), args.backlog_before_key)
        backlog_after = parse_float(row.get(args.backlog_after_key), args.backlog_after_key)
        backlog_regressions = parse_int(
            row.get(args.backlog_regressions_key, 0),
            args.backlog_regressions_key,
        )
        critical_regressions = parse_int(
            row.get(args.critical_regressions_key, 0),
            args.critical_regressions_key,
        )
        backlog_overflow_events = parse_int(
            row.get(args.backlog_overflow_events_key, 0),
            args.backlog_overflow_events_key,
        )
        capa_failures = parse_int(row.get(args.capa_failures_key, 0), args.capa_failures_key)
        budget_used = parse_float(row.get(args.budget_used_key), args.budget_used_key)
        budget_total = parse_float(row.get(args.budget_total_key), args.budget_total_key)

        backlog_growth = backlog_after - backlog_before
        if operations < 0:
            fail(f"operations for {args.operations_key} must be >= 0; got {operations}")
        if backlog_before < 0:
            fail(f"backlog_before for {args.backlog_before_key} must be >= 0; got {backlog_before}")
        if backlog_after < 0:
            fail(f"backlog_after for {args.backlog_after_key} must be >= 0; got {backlog_after}")
        if backlog_regressions < 0:
            fail(
                f"backlog_regressions for {args.backlog_regressions_key} must be >= 0; "
                f"got {backlog_regressions}"
            )
        if critical_regressions < 0:
            fail(
                f"critical_regressions for {args.critical_regressions_key} must be >= 0; "
                f"got {critical_regressions}"
            )
        if backlog_overflow_events < 0:
            fail(
                f"backlog_overflow_events for {args.backlog_overflow_events_key} must be >= 0; "
                f"got {backlog_overflow_events}"
            )
        if capa_failures < 0:
            fail(f"capa_failures for {args.capa_failures_key} must be >= 0; got {capa_failures}")
        if budget_used < 0:
            fail(f"budget_used for {args.budget_used_key} must be >= 0; got {budget_used}")
        if budget_total <= 0:
            fail(f"budget_total for {args.budget_total_key} must be > 0; got {budget_total}")
        if budget_used > budget_total:
            fail(f"budget_used={budget_used} cannot exceed budget_total={budget_total}")

        if backlog_regressions > operations:
            fail(f"backlog_regressions={backlog_regressions} cannot exceed operations={operations}")
        if critical_regressions > backlog_regressions:
            fail(
                f"critical_regressions={critical_regressions} cannot exceed "
                f"backlog_regressions={backlog_regressions}"
            )
        if capa_failures > operations:
            fail(f"capa_failures={capa_failures} cannot exceed operations={operations}")

        total_operations += operations
        total_backlog_regressions += backlog_regressions
        total_critical_regressions += critical_regressions
        total_backlog_overflow_events += backlog_overflow_events
        total_capa_failures += capa_failures
        total_budget_used += budget_used
        total_budget_total += budget_total
        total_backlog_growth += backlog_growth

        window = str(row.get(args.window_key, "default"))
        window_operations[window] = window_operations.get(window, 0.0) + operations
        window_regressions[window] = window_regressions.get(window, 0) + backlog_regressions
        window_budget_used[window] = window_budget_used.get(window, 0.0) + budget_used
        window_budget_total[window] = window_budget_total.get(window, 0.0) + budget_total
        window_backlog_growth[window] = window_backlog_growth.get(window, 0.0) + backlog_growth

    if total_operations < args.min_total_operations:
        fail(f"total_operations={total_operations} < min_total_operations={args.min_total_operations}")

    if total_budget_total <= 0:
        fail(f"total_budget_total={total_budget_total} must be > 0")

    total_regression_rate = total_backlog_regressions / total_operations
    if total_regression_rate > args.max_total_regression_rate:
        fail(
            f"total_regression_rate={total_regression_rate} > "
            f"max_total_regression_rate={args.max_total_regression_rate}"
        )

    average_backlog_growth = total_backlog_growth / total_operations
    if average_backlog_growth > args.max_average_backlog_growth:
        fail(
            f"average_backlog_growth={average_backlog_growth} > "
            f"max_average_backlog_growth={args.max_average_backlog_growth}"
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

    if total_backlog_overflow_events > args.max_total_overflow_events:
        fail(
            f"total_backlog_overflow_events={total_backlog_overflow_events} > "
            f"max_total_overflow_events={args.max_total_overflow_events}"
        )

    if total_capa_failures > args.max_total_capa_failures:
        fail(
            f"total_capa_failures={total_capa_failures} > "
            f"max_total_capa_failures={args.max_total_capa_failures}"
        )

    for window in sorted(window_operations):
        operations = window_operations[window]
        if operations <= 0:
            fail(f"window={window} operations={operations} must be > 0")

        window_regression_rate = window_regressions[window] / operations
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
