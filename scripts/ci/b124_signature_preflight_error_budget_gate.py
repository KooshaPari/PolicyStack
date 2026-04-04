#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E124 [lane B] signature preflight error budget gate failed: {message}",
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
    parser.add_argument("--total-key", default="total")
    parser.add_argument("--errors-key", default="errors")
    parser.add_argument("--critical-errors-key", default="critical_errors")
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument("--max-window-error-rate", type=float, default=0.0)
    parser.add_argument("--max-critical-errors", type=int, default=0)
    parser.add_argument("--max-total-errors", type=int, default=0)
    parser.add_argument("--min-total-samples", type=float, default=1.0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_samples = 0.0
    total_errors = 0
    total_critical_errors = 0
    window_totals: dict[str, float] = {}
    window_errors: dict[str, int] = {}

    for row in records:
        samples = parse_float(row.get(args.total_key), args.total_key)
        errors = parse_int(row.get(args.errors_key, 0), args.errors_key)
        critical_errors = parse_int(
            row.get(args.critical_errors_key, 0),
            args.critical_errors_key,
        )
        if samples < 0:
            fail(f"samples for {args.total_key} must be >= 0; got {samples}")
        if errors < 0:
            fail(f"errors for {args.errors_key} must be >= 0; got {errors}")
        if critical_errors < 0:
            fail(
                f"critical errors for {args.critical_errors_key} must be >= 0; got {critical_errors}"
            )

        total_samples += samples
        total_errors += errors
        total_critical_errors += critical_errors

        window = str(row.get(args.window_key, "default"))
        window_totals[window] = window_totals.get(window, 0.0) + samples
        window_errors[window] = window_errors.get(window, 0) + errors

    if total_samples < args.min_total_samples:
        fail(f"total_samples={total_samples} < min_total_samples={args.min_total_samples}")

    error_rate = total_errors / total_samples
    if error_rate > args.max_error_rate:
        fail(f"error_rate={error_rate} > max_error_rate={args.max_error_rate}")

    if total_critical_errors > args.max_critical_errors:
        fail(
            f"critical_errors={total_critical_errors} > max_critical_errors={args.max_critical_errors}"
        )

    if total_errors > args.max_total_errors:
        fail(f"total_errors={total_errors} > max_total_errors={args.max_total_errors}")

    for window in sorted(window_totals):
        window_total = window_totals[window]
        if window_total <= 0:
            fail(f"window={window} total_samples={window_total} must be > 0")
        window_error_rate = window_errors[window] / window_total
        if window_error_rate > args.max_window_error_rate:
            fail(
                f"window={window} error_rate={window_error_rate} > max_window_error_rate="
                f"{args.max_window_error_rate}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
