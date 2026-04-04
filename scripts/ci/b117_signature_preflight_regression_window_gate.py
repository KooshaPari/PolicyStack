#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E117 [lane B] signature preflight regression window gate failed: {message}",
        file=sys.stderr,
    )
    raise SystemExit(2)


def parse_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid numeric value for {field}: {value!r}")


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
    parser.add_argument("--score-key", default="regression_score")
    parser.add_argument("--regression-threshold", type=float, default=0.0)
    parser.add_argument("--max-regression-count", type=int, default=0)
    parser.add_argument("--max-overall-average", type=float, default=0.0)
    parser.add_argument("--max-window-average", type=float, default=0.0)
    parser.add_argument("--min-window-samples", type=int, default=1)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    if args.min_window_samples < 1:
        fail("min-window-samples must be >= 1")

    regression_count = 0
    total = 0.0
    window_totals: dict[str, float] = {}
    window_counts: dict[str, int] = {}

    for row in records:
        score = parse_float(row.get(args.score_key), args.score_key)
        total += score
        if score > args.regression_threshold:
            regression_count += 1

        window = str(row.get(args.window_key, "default"))
        window_totals[window] = window_totals.get(window, 0.0) + score
        window_counts[window] = window_counts.get(window, 0) + 1

    overall_average = total / len(records)
    if overall_average > args.max_overall_average:
        fail(
            f"overall_average={overall_average} > max_overall_average={args.max_overall_average}"
        )

    if regression_count > args.max_regression_count:
        fail(
            f"regression_count={regression_count} > max_regression_count={args.max_regression_count}"
        )

    for window, count in sorted(window_counts.items()):
        if count < args.min_window_samples:
            fail(
                f"window={window} has samples={count} < min_window_samples={args.min_window_samples}"
            )
        average = window_totals[window] / count
        if average > args.max_window_average:
            fail(
                f"window={window} average={average} > max_window_average={args.max_window_average}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
