#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E139 [lane B] capa reclaim regression window gate failed: {message}",
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
    parser.add_argument("--regressions-key", default="regressions")
    parser.add_argument("--critical-regressions-key", default="critical_regressions")
    parser.add_argument("--reclaim-failures-key", default="reclaim_failures")
    parser.add_argument("--reclaim-latency-ms-key", default="reclaim_latency_ms")
    parser.add_argument("--min-total-operations", type=float, default=1.0)
    parser.add_argument("--max-total-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-window-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-total-critical-regressions", type=int, default=0)
    parser.add_argument("--max-total-reclaim-failures", type=int, default=0)
    parser.add_argument("--max-reclaim-latency-ms", type=float, default=0.0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_operations = 0.0
    total_regressions = 0
    total_critical_regressions = 0
    total_reclaim_failures = 0
    max_reclaim_latency_ms = 0.0
    window_operations: dict[str, float] = {}
    window_regressions: dict[str, int] = {}

    for row in records:
        operations = parse_float(row.get(args.operations_key), args.operations_key)
        regressions = parse_int(row.get(args.regressions_key, 0), args.regressions_key)
        critical_regressions = parse_int(
            row.get(args.critical_regressions_key, 0),
            args.critical_regressions_key,
        )
        reclaim_failures = parse_int(
            row.get(args.reclaim_failures_key, 0),
            args.reclaim_failures_key,
        )
        reclaim_latency_ms = parse_float(
            row.get(args.reclaim_latency_ms_key, 0),
            args.reclaim_latency_ms_key,
        )

        if operations < 0:
            fail(f"operations for {args.operations_key} must be >= 0; got {operations}")
        if regressions < 0:
            fail(f"regressions for {args.regressions_key} must be >= 0; got {regressions}")
        if critical_regressions < 0:
            fail(
                f"critical regressions for {args.critical_regressions_key} must be >= 0; got "
                f"{critical_regressions}"
            )
        if reclaim_failures < 0:
            fail(
                f"reclaim_failures for {args.reclaim_failures_key} must be >= 0; got "
                f"{reclaim_failures}"
            )
        if reclaim_latency_ms < 0:
            fail(
                f"reclaim_latency_ms for {args.reclaim_latency_ms_key} must be >= 0; got "
                f"{reclaim_latency_ms}"
            )
        if regressions > operations:
            fail(f"regressions={regressions} cannot exceed operations={operations}")
        if critical_regressions > regressions:
            fail(
                f"critical_regressions={critical_regressions} cannot exceed regressions={regressions}"
            )
        if reclaim_failures > operations:
            fail(f"reclaim_failures={reclaim_failures} cannot exceed operations={operations}")

        total_operations += operations
        total_regressions += regressions
        total_critical_regressions += critical_regressions
        total_reclaim_failures += reclaim_failures
        max_reclaim_latency_ms = max(max_reclaim_latency_ms, reclaim_latency_ms)

        window = str(row.get(args.window_key, "default"))
        window_operations[window] = window_operations.get(window, 0.0) + operations
        window_regressions[window] = window_regressions.get(window, 0) + regressions

    if total_operations < args.min_total_operations:
        fail(f"total_operations={total_operations} < min_total_operations={args.min_total_operations}")

    total_regression_rate = total_regressions / total_operations
    if total_regression_rate > args.max_total_regression_rate:
        fail(
            f"total_regression_rate={total_regression_rate} > max_total_regression_rate="
            f"{args.max_total_regression_rate}"
        )

    if total_critical_regressions > args.max_total_critical_regressions:
        fail(
            f"total_critical_regressions={total_critical_regressions} > "
            f"max_total_critical_regressions={args.max_total_critical_regressions}"
        )

    if total_reclaim_failures > args.max_total_reclaim_failures:
        fail(
            f"total_reclaim_failures={total_reclaim_failures} > "
            f"max_total_reclaim_failures={args.max_total_reclaim_failures}"
        )

    if max_reclaim_latency_ms > args.max_reclaim_latency_ms:
        fail(
            f"max_reclaim_latency_ms={max_reclaim_latency_ms} > "
            f"max_reclaim_latency_ms={args.max_reclaim_latency_ms}"
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
