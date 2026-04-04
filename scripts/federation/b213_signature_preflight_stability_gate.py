#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E213 [lane B] signature window budget gate failed: {message}",
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
    parser.add_argument("--budget-used-key", default="budget_used")
    parser.add_argument("--budget-total-key", default="budget_total")
    parser.add_argument("--window-budget-overruns-key", default="window_budget_overruns")
    parser.add_argument("--min-total-samples", type=float, default=1.0)
    parser.add_argument("--max-total-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-window-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-total-window-budget-overruns", type=int, default=0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_samples = 0.0
    total_budget_used = 0.0
    total_budget_total = 0.0
    total_window_budget_overruns = 0
    window_budget_used: dict[str, float] = {}
    window_budget_total: dict[str, float] = {}

    for row in records:
        samples = parse_float(row.get(args.samples_key), args.samples_key)
        budget_used = parse_float(row.get(args.budget_used_key), args.budget_used_key)
        budget_total = parse_float(row.get(args.budget_total_key), args.budget_total_key)
        window_budget_overruns = parse_int(
            row.get(args.window_budget_overruns_key, 0),
            args.window_budget_overruns_key,
        )

        if samples < 0:
            fail(f"samples for {args.samples_key} must be >= 0; got {samples}")
        if budget_used < 0:
            fail(f"budget_used for {args.budget_used_key} must be >= 0; got {budget_used}")
        if budget_total <= 0:
            fail(f"budget_total for {args.budget_total_key} must be > 0; got {budget_total}")
        if budget_used > budget_total:
            fail(f"budget_used={budget_used} cannot exceed budget_total={budget_total}")
        if window_budget_overruns < 0:
            fail(
                f"window_budget_overruns for {args.window_budget_overruns_key} must be >= 0; "
                f"got {window_budget_overruns}"
            )

        total_samples += samples
        total_budget_used += budget_used
        total_budget_total += budget_total
        total_window_budget_overruns += window_budget_overruns

        window = str(row.get(args.window_key, "default"))
        window_budget_used[window] = window_budget_used.get(window, 0.0) + budget_used
        window_budget_total[window] = window_budget_total.get(window, 0.0) + budget_total

    if total_samples < args.min_total_samples:
        fail(f"total_samples={total_samples} < min_total_samples={args.min_total_samples}")

    if total_budget_total <= 0:
        fail(f"total_budget_total={total_budget_total} must be > 0")

    total_budget_usage_ratio = total_budget_used / total_budget_total
    if total_budget_usage_ratio > args.max_total_budget_usage_ratio:
        fail(
            f"total_budget_usage_ratio={total_budget_usage_ratio} > "
            f"max_total_budget_usage_ratio={args.max_total_budget_usage_ratio}"
        )

    if total_window_budget_overruns > args.max_total_window_budget_overruns:
        fail(
            f"total_window_budget_overruns={total_window_budget_overruns} > "
            f"max_total_window_budget_overruns={args.max_total_window_budget_overruns}"
        )

    for window in sorted(window_budget_used):
        window_total = window_budget_total[window]
        if window_total <= 0:
            fail(f"window={window} budget_total={window_total} must be > 0")
        window_budget_usage_ratio = window_budget_used[window] / window_total
        if window_budget_usage_ratio > args.max_window_budget_usage_ratio:
            fail(
                f"window={window} budget_usage_ratio={window_budget_usage_ratio} > "
                f"max_window_budget_usage_ratio={args.max_window_budget_usage_ratio}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
