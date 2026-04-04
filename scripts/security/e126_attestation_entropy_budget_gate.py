#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E126 attestation entropy budget gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--max-total-entropy", type=float, default=0.0)
    parser.add_argument("--max-average-entropy", type=float, default=0.0)
    args = parser.parse_args()

    if args.max_total_entropy < 0:
        fail(f"max-total-entropy must be non-negative: {args.max_total_entropy}")
    if args.max_average_entropy < 0:
        fail(f"max-average-entropy must be non-negative: {args.max_average_entropy}")

    rows = load_rows(pathlib.Path(args.attestations))
    if not rows:
        fail("attestations payload must contain rows")

    entropy_values = []
    for row in rows:
        if isinstance(row, dict):
            entropy_values.append(parse_float(row.get(args.entropy_col), args.entropy_col))

    if not entropy_values:
        fail("attestations payload must contain dict rows with entropy values")

    total_entropy = sum(entropy_values)
    average_entropy = total_entropy / len(entropy_values)
    if total_entropy > args.max_total_entropy:
        fail(
            f"total_entropy={total_entropy:.6f} exceeds max_total_entropy={args.max_total_entropy}"
        )
    if average_entropy > args.max_average_entropy:
        fail(
            f"average_entropy={average_entropy:.6f} exceeds max_average_entropy={args.max_average_entropy}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

