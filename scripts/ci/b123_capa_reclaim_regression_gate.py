#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E123 [lane B] capa reclaim regression gate failed: {message}",
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
    parser.add_argument("--reclaim-ms-key", default="reclaim_ms")
    parser.add_argument("--rollback-flag-key", default="rolled_back")
    parser.add_argument("--regression-threshold", type=float, default=0.0)
    parser.add_argument("--max-regression-count", type=int, default=0)
    parser.add_argument("--max-average-regression-score", type=float, default=0.0)
    parser.add_argument("--max-average-reclaim-ms", type=float, default=0.0)
    parser.add_argument("--max-rollback-count", type=int, default=0)
    parser.add_argument("--max-window-average-regression-score", type=float, default=0.0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    regression_total = 0.0
    reclaim_ms_total = 0.0
    regression_count = 0
    rollback_count = 0
    window_totals: dict[str, float] = {}
    window_counts: dict[str, int] = {}

    for row in records:
        regression_score = parse_float(row.get(args.regression_score_key), args.regression_score_key)
        reclaim_ms = parse_float(row.get(args.reclaim_ms_key, 0), args.reclaim_ms_key)
        rolled_back = parse_int(row.get(args.rollback_flag_key, 0), args.rollback_flag_key)

        regression_total += regression_score
        reclaim_ms_total += reclaim_ms
        if regression_score > args.regression_threshold:
            regression_count += 1
        rollback_count += 1 if rolled_back else 0

        window = str(row.get(args.window_key, "default"))
        window_totals[window] = window_totals.get(window, 0.0) + regression_score
        window_counts[window] = window_counts.get(window, 0) + 1

    average_regression_score = regression_total / len(records)
    if average_regression_score > args.max_average_regression_score:
        fail(
            f"average_regression_score={average_regression_score} > max_average_regression_score="
            f"{args.max_average_regression_score}"
        )

    average_reclaim_ms = reclaim_ms_total / len(records)
    if average_reclaim_ms > args.max_average_reclaim_ms:
        fail(
            f"average_reclaim_ms={average_reclaim_ms} > max_average_reclaim_ms="
            f"{args.max_average_reclaim_ms}"
        )

    if regression_count > args.max_regression_count:
        fail(f"regression_count={regression_count} > max_regression_count={args.max_regression_count}")

    if rollback_count > args.max_rollback_count:
        fail(f"rollback_count={rollback_count} > max_rollback_count={args.max_rollback_count}")

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
