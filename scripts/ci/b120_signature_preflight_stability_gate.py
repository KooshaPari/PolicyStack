#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E120 [lane B] signature preflight stability gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--stability-key", default="stability_score")
    parser.add_argument("--variance-key", default="variance")
    parser.add_argument("--min-average-stability", type=float, default=0.0)
    parser.add_argument("--min-window-average-stability", type=float, default=0.0)
    parser.add_argument("--min-stability-threshold", type=float, default=0.0)
    parser.add_argument("--max-unstable-count", type=int, default=0)
    parser.add_argument("--max-average-variance", type=float, default=0.0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    stability_total = 0.0
    variance_total = 0.0
    unstable_count = 0
    window_stability_totals: dict[str, float] = {}
    window_counts: dict[str, int] = {}

    for row in records:
        stability = parse_float(row.get(args.stability_key), args.stability_key)
        variance = parse_float(row.get(args.variance_key, 0), args.variance_key)
        stability_total += stability
        variance_total += variance
        if stability < args.min_stability_threshold:
            unstable_count += 1

        window = str(row.get(args.window_key, "default"))
        window_stability_totals[window] = window_stability_totals.get(window, 0.0) + stability
        window_counts[window] = window_counts.get(window, 0) + 1

    average_stability = stability_total / len(records)
    if average_stability < args.min_average_stability:
        fail(
            f"average_stability={average_stability} < min_average_stability="
            f"{args.min_average_stability}"
        )

    average_variance = variance_total / len(records)
    if average_variance > args.max_average_variance:
        fail(
            f"average_variance={average_variance} > max_average_variance="
            f"{args.max_average_variance}"
        )

    if unstable_count > args.max_unstable_count:
        fail(f"unstable_count={unstable_count} > max_unstable_count={args.max_unstable_count}")

    for window, count in sorted(window_counts.items()):
        average = window_stability_totals[window] / count
        if average < args.min_window_average_stability:
            fail(
                f"window={window} average_stability={average} < min_window_average_stability="
                f"{args.min_window_average_stability}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
