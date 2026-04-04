#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E132 [lane B] signature preflight entropy gate failed: {message}",
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
    parser.add_argument("--entropy-key", default="entropy")
    parser.add_argument("--coverage-key", default="coverage")
    parser.add_argument("--collision-count-key", default="collision_count")
    parser.add_argument("--min-average-entropy", type=float, default=0.0)
    parser.add_argument("--min-window-average-entropy", type=float, default=0.0)
    parser.add_argument("--max-collision-count", type=int, default=0)
    parser.add_argument("--min-coverage", type=float, default=0.0)
    parser.add_argument("--max-coverage", type=float, default=1.0)
    args = parser.parse_args()

    path = pathlib.Path(args.input)
    records = load_records(path, infer_format(path, args.format), args.records_key)

    entropy_total = 0.0
    collision_total = 0
    window_entropy_totals: dict[str, float] = {}
    window_counts: dict[str, int] = {}

    for row in records:
        entropy = parse_float(row.get(args.entropy_key), args.entropy_key)
        coverage = parse_float(row.get(args.coverage_key, args.max_coverage), args.coverage_key)
        collision_count = parse_int(row.get(args.collision_count_key, 0), args.collision_count_key)

        if entropy < 0:
            fail(f"entropy for {args.entropy_key} must be >= 0; got {entropy}")
        if coverage < args.min_coverage or coverage > args.max_coverage:
            fail(
                f"coverage={coverage} must be within [{args.min_coverage}, "
                f"{args.max_coverage}]"
            )
        if collision_count < 0:
            fail(
                f"collision count for {args.collision_count_key} must be >= 0; got "
                f"{collision_count}"
            )

        entropy_total += entropy
        collision_total += collision_count

        window = str(row.get(args.window_key, "default"))
        window_entropy_totals[window] = window_entropy_totals.get(window, 0.0) + entropy
        window_counts[window] = window_counts.get(window, 0) + 1

    average_entropy = entropy_total / len(records)
    if average_entropy < args.min_average_entropy:
        fail(f"average_entropy={average_entropy} < min_average_entropy={args.min_average_entropy}")

    if collision_total > args.max_collision_count:
        fail(
            f"collision_count={collision_total} > max_collision_count={args.max_collision_count}"
        )

    for window, count in sorted(window_counts.items()):
        window_average_entropy = window_entropy_totals[window] / count
        if window_average_entropy < args.min_window_average_entropy:
            fail(
                f"window={window} average_entropy={window_average_entropy} < "
                f"min_window_average_entropy={args.min_window_average_entropy}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
