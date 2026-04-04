#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E119 custody gap burst gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(value: object, field: str) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {value!r}")


def load_rows(path: pathlib.Path) -> list[dict]:
    try:
        if path.suffix.lower() == ".csv":
            return list(csv.DictReader(path.read_text().splitlines()))
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid custody input: {exc}")

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("records", "items", "entries", "transitions", "attestations"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
    fail("custody payload must be list or object with records/items/entries/transitions/attestations")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", required=True)
    parser.add_argument("--gap-col", default="gap_seconds")
    parser.add_argument("--gap-threshold", type=float, default=300.0)
    parser.add_argument("--burst-size", type=int, default=3)
    parser.add_argument("--max-bursts", type=int, default=0)
    args = parser.parse_args()

    if args.burst_size <= 0:
        fail(f"burst-size must be positive: {args.burst_size}")

    rows = load_rows(pathlib.Path(args.records))
    if not rows:
        fail("records payload must contain rows")

    streak = 0
    bursts = 0
    in_burst = False

    for row in rows:
        if not isinstance(row, dict):
            continue
        gap_value = parse_float(row.get(args.gap_col), args.gap_col)
        if gap_value > args.gap_threshold:
            streak += 1
            if streak >= args.burst_size and not in_burst:
                bursts += 1
                in_burst = True
        else:
            streak = 0
            in_burst = False

    if bursts > args.max_bursts:
        fail(f"bursts={bursts} exceeds max_bursts={args.max_bursts}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
