#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E126 [lane B] scheduler queue regression gate failed: {message}",
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
    parser.add_argument("--regression-score-key", default="regression_score")
    parser.add_argument("--queue-depth-key", default="queue_depth")
    parser.add_argument("--regressed-flag-key", default="regressed")
    parser.add_argument("--regression-threshold", type=float, default=0.0)
    parser.add_argument("--max-regression-count", type=int, default=0)
    parser.add_argument("--max-average-regression-score", type=float, default=0.0)
    parser.add_argument("--max-window-average-regression-score", type=float, default=0.0)
    parser.add_argument("--max-queue-depth", type=float, default=0.0)
    parser.add_argument("--max-regressed-count", type=int, default=0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    regression_total = 0.0
    regression_count = 0
    regressed_count = 0
    max_queue_depth = 0.0
    window_totals: dict[str, float] = {}
    window_counts: dict[str, int] = {}

    for row in records:
        regression_score = parse_float(row.get(args.regression_score_key), args.regression_score_key)
        queue_depth = parse_float(row.get(args.queue_depth_key, 0), args.queue_depth_key)
        regressed = parse_int(row.get(args.regressed_flag_key, 0), args.regressed_flag_key)

        regression_total += regression_score
        max_queue_depth = max(max_queue_depth, queue_depth)
        if regression_score > args.regression_threshold:
            regression_count += 1
        regressed_count += 1 if regressed else 0

        window = str(row.get(args.window_key, "default"))
        window_totals[window] = window_totals.get(window, 0.0) + regression_score
        window_counts[window] = window_counts.get(window, 0) + 1

    average_regression_score = regression_total / len(records)
    if average_regression_score > args.max_average_regression_score:
        fail(
            f"average_regression_score={average_regression_score} > max_average_regression_score="
            f"{args.max_average_regression_score}"
        )

    if regression_count > args.max_regression_count:
        fail(f"regression_count={regression_count} > max_regression_count={args.max_regression_count}")

    if regressed_count > args.max_regressed_count:
        fail(f"regressed_count={regressed_count} > max_regressed_count={args.max_regressed_count}")

    if max_queue_depth > args.max_queue_depth:
        fail(f"max_queue_depth={max_queue_depth} > max_queue_depth={args.max_queue_depth}")

    for window, count in sorted(window_counts.items()):
        average = window_totals[window] / count
        if average > args.max_window_average_regression_score:
            fail(
                f"window={window} average_regression_score={average} > "
                f"max_window_average_regression_score={args.max_window_average_regression_score}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
