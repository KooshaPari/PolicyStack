#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E135 [lane B] capa reclaim error budget gate failed: {message}",
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
    parser.add_argument("--errors-key", default="errors")
    parser.add_argument("--critical-errors-key", default="critical_errors")
    parser.add_argument("--error-budget-breach-flag-key", default="error_budget_breached")
    parser.add_argument("--max-total-error-rate", type=float, default=0.0)
    parser.add_argument("--max-window-error-rate", type=float, default=0.0)
    parser.add_argument("--max-total-critical-errors", type=int, default=0)
    parser.add_argument("--max-error-budget-breach-count", type=int, default=0)
    parser.add_argument("--min-total-operations", type=float, default=1.0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_operations = 0.0
    total_errors = 0
    total_critical_errors = 0
    error_budget_breach_count = 0
    window_operations: dict[str, float] = {}
    window_errors: dict[str, int] = {}

    for row in records:
        operations = parse_float(row.get(args.operations_key), args.operations_key)
        errors = parse_int(row.get(args.errors_key, 0), args.errors_key)
        critical_errors = parse_int(
            row.get(args.critical_errors_key, 0),
            args.critical_errors_key,
        )
        error_budget_breached = parse_int(
            row.get(args.error_budget_breach_flag_key, 0),
            args.error_budget_breach_flag_key,
        )

        if operations < 0:
            fail(f"operations for {args.operations_key} must be >= 0; got {operations}")
        if errors < 0:
            fail(f"errors for {args.errors_key} must be >= 0; got {errors}")
        if critical_errors < 0:
            fail(
                f"critical errors for {args.critical_errors_key} must be >= 0; got "
                f"{critical_errors}"
            )
        if errors > operations:
            fail(f"errors={errors} cannot exceed operations={operations}")
        if critical_errors > errors:
            fail(f"critical_errors={critical_errors} cannot exceed errors={errors}")

        total_operations += operations
        total_errors += errors
        total_critical_errors += critical_errors
        error_budget_breach_count += 1 if error_budget_breached else 0

        window = str(row.get(args.window_key, "default"))
        window_operations[window] = window_operations.get(window, 0.0) + operations
        window_errors[window] = window_errors.get(window, 0) + errors

    if total_operations < args.min_total_operations:
        fail(f"total_operations={total_operations} < min_total_operations={args.min_total_operations}")

    total_error_rate = total_errors / total_operations
    if total_error_rate > args.max_total_error_rate:
        fail(
            f"total_error_rate={total_error_rate} > max_total_error_rate="
            f"{args.max_total_error_rate}"
        )

    if total_critical_errors > args.max_total_critical_errors:
        fail(
            f"total_critical_errors={total_critical_errors} > "
            f"max_total_critical_errors={args.max_total_critical_errors}"
        )

    if error_budget_breach_count > args.max_error_budget_breach_count:
        fail(
            f"error_budget_breach_count={error_budget_breach_count} > "
            f"max_error_budget_breach_count={args.max_error_budget_breach_count}"
        )

    for window in sorted(window_operations):
        operations = window_operations[window]
        if operations <= 0:
            fail(f"window={window} operations={operations} must be > 0")
        window_error_rate = window_errors[window] / operations
        if window_error_rate > args.max_window_error_rate:
            fail(
                f"window={window} error_rate={window_error_rate} > "
                f"max_window_error_rate={args.max_window_error_rate}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

