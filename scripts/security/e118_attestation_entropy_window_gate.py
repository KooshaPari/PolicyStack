#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E118 attestation entropy window gate failed: {message}", file=sys.stderr)
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
        fail(f"invalid attestations input: {exc}")

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("attestations", "records", "items", "entries", "transitions"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
    fail("attestations payload must be list or object with attestations/records/items/entries/transitions")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attestations", required=True)
    parser.add_argument("--entropy-col", default="entropy")
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--max-window-avg", type=float, default=1.0)
    parser.add_argument("--spike-threshold", type=float, default=2.0)
    parser.add_argument("--max-window-spikes", type=int, default=1)
    parser.add_argument("--max-window-violations", type=int, default=0)
    args = parser.parse_args()

    if args.window_size <= 0:
        fail(f"window-size must be positive: {args.window_size}")

    rows = load_rows(pathlib.Path(args.attestations))
    if not rows:
        fail("attestations payload must contain rows")

    entropy_values = []
    for row in rows:
        if isinstance(row, dict):
            entropy_values.append(parse_float(row.get(args.entropy_col), args.entropy_col))

    if not entropy_values:
        fail("attestations payload must contain dict rows with entropy values")

    violations = 0
    for start in range(0, len(entropy_values) - args.window_size + 1):
        window = entropy_values[start : start + args.window_size]
        avg_entropy = sum(window) / len(window)
        spike_count = sum(1 for value in window if value > args.spike_threshold)
        if avg_entropy > args.max_window_avg or spike_count > args.max_window_spikes:
            violations += 1

    if violations > args.max_window_violations:
        fail(
            f"window_violations={violations} exceeds max_window_violations={args.max_window_violations}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
