#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E125 [lane B] signature preflight regression rate gate failed: {message}",
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
    parser.add_argument("--regressions-key", default="regressions")
    parser.add_argument("--critical-regressions-key", default="critical_regressions")
    parser.add_argument("--max-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-window-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-total-regressions", type=int, default=0)
    parser.add_argument("--max-critical-regressions", type=int, default=0)
    parser.add_argument("--min-total-samples", type=float, default=1.0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_samples = 0.0
    total_regressions = 0
    total_critical_regressions = 0
    window_totals: dict[str, float] = {}
    window_regressions: dict[str, int] = {}

    for row in records:
        samples = parse_float(row.get(args.total_key), args.total_key)
        regressions = parse_int(row.get(args.regressions_key, 0), args.regressions_key)
        critical_regressions = parse_int(
            row.get(args.critical_regressions_key, 0),
            args.critical_regressions_key,
        )
        if samples < 0:
            fail(f"samples for {args.total_key} must be >= 0; got {samples}")
        if regressions < 0:
            fail(f"regressions for {args.regressions_key} must be >= 0; got {regressions}")
        if critical_regressions < 0:
            fail(
                f"critical regressions for {args.critical_regressions_key} must be >= 0; got "
                f"{critical_regressions}"
            )

        total_samples += samples
        total_regressions += regressions
        total_critical_regressions += critical_regressions

        window = str(row.get(args.window_key, "default"))
        window_totals[window] = window_totals.get(window, 0.0) + samples
        window_regressions[window] = window_regressions.get(window, 0) + regressions

    if total_samples < args.min_total_samples:
        fail(f"total_samples={total_samples} < min_total_samples={args.min_total_samples}")

    regression_rate = total_regressions / total_samples
    if regression_rate > args.max_regression_rate:
        fail(f"regression_rate={regression_rate} > max_regression_rate={args.max_regression_rate}")

    if total_regressions > args.max_total_regressions:
        fail(
            f"total_regressions={total_regressions} > max_total_regressions={args.max_total_regressions}"
        )

    if total_critical_regressions > args.max_critical_regressions:
        fail(
            f"critical_regressions={total_critical_regressions} > max_critical_regressions="
            f"{args.max_critical_regressions}"
        )

    for window in sorted(window_totals):
        window_total = window_totals[window]
        if window_total <= 0:
            fail(f"window={window} total_samples={window_total} must be > 0")
        window_regression_rate = window_regressions[window] / window_total
        if window_regression_rate > args.max_window_regression_rate:
            fail(
                f"window={window} regression_rate={window_regression_rate} > "
                f"max_window_regression_rate={args.max_window_regression_rate}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
