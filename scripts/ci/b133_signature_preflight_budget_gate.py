#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E133 [lane B] signature preflight budget gate failed: {message}",
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
    parser.add_argument("--budget-used-key", default="budget_used")
    parser.add_argument("--budget-total-key", default="budget_total")
    parser.add_argument("--budget-breach-flag-key", default="budget_breached")
    parser.add_argument("--retry-count-key", default="retry_count")
    parser.add_argument("--max-total-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-window-budget-usage-ratio", type=float, default=0.0)
    parser.add_argument("--max-budget-breach-count", type=int, default=0)
    parser.add_argument("--max-total-retry-count", type=int, default=0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    total_budget_used = 0.0
    total_budget_total = 0.0
    budget_breach_count = 0
    total_retry_count = 0
    window_budget_used: dict[str, float] = {}
    window_budget_total: dict[str, float] = {}

    for row in records:
        budget_used = parse_float(row.get(args.budget_used_key), args.budget_used_key)
        budget_total = parse_float(row.get(args.budget_total_key), args.budget_total_key)
        budget_breached = parse_int(
            row.get(args.budget_breach_flag_key, 0),
            args.budget_breach_flag_key,
        )
        retry_count = parse_int(row.get(args.retry_count_key, 0), args.retry_count_key)

        if budget_used < 0:
            fail(f"budget_used for {args.budget_used_key} must be >= 0; got {budget_used}")
        if budget_total <= 0:
            fail(f"budget_total for {args.budget_total_key} must be > 0; got {budget_total}")
        if budget_used > budget_total:
            fail(f"budget_used={budget_used} cannot exceed budget_total={budget_total}")
        if retry_count < 0:
            fail(f"retry_count for {args.retry_count_key} must be >= 0; got {retry_count}")

        total_budget_used += budget_used
        total_budget_total += budget_total
        budget_breach_count += 1 if budget_breached else 0
        total_retry_count += retry_count

        window = str(row.get(args.window_key, "default"))
        window_budget_used[window] = window_budget_used.get(window, 0.0) + budget_used
        window_budget_total[window] = window_budget_total.get(window, 0.0) + budget_total

    total_usage_ratio = total_budget_used / total_budget_total
    if total_usage_ratio > args.max_total_budget_usage_ratio:
        fail(
            f"total_budget_usage_ratio={total_usage_ratio} > max_total_budget_usage_ratio="
            f"{args.max_total_budget_usage_ratio}"
        )

    if budget_breach_count > args.max_budget_breach_count:
        fail(
            f"budget_breach_count={budget_breach_count} > "
            f"max_budget_breach_count={args.max_budget_breach_count}"
        )

    if total_retry_count > args.max_total_retry_count:
        fail(
            f"total_retry_count={total_retry_count} > "
            f"max_total_retry_count={args.max_total_retry_count}"
        )

    for window in sorted(window_budget_used):
        window_total = window_budget_total[window]
        if window_total <= 0:
            fail(f"window={window} budget_total={window_total} must be > 0")
        window_usage_ratio = window_budget_used[window] / window_total
        if window_usage_ratio > args.max_window_budget_usage_ratio:
            fail(
                f"window={window} budget_usage_ratio={window_usage_ratio} > "
                f"max_window_budget_usage_ratio={args.max_window_budget_usage_ratio}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
