#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E122 attestation entropy spike gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--spike-threshold", type=float, default=2.0)
    parser.add_argument("--max-spikes", type=int, default=0)
    parser.add_argument("--max-spike-rate", type=float, default=0.0)
    args = parser.parse_args()

    if args.max_spikes < 0:
        fail(f"max-spikes must be non-negative: {args.max_spikes}")
    if args.max_spike_rate < 0 or args.max_spike_rate > 1:
        fail(f"max-spike-rate must be between 0 and 1: {args.max_spike_rate}")

    rows = load_rows(pathlib.Path(args.attestations))
    if not rows:
        fail("attestations payload must contain rows")

    entropy_values = []
    for row in rows:
        if isinstance(row, dict):
            entropy_values.append(parse_float(row.get(args.entropy_col), args.entropy_col))

    if not entropy_values:
        fail("attestations payload must contain dict rows with entropy values")

    spikes = sum(1 for value in entropy_values if value > args.spike_threshold)
    spike_rate = spikes / len(entropy_values)

    if spikes > args.max_spikes:
        fail(f"spikes={spikes} exceeds max_spikes={args.max_spikes}")
    if spike_rate > args.max_spike_rate:
        fail(f"spike_rate={spike_rate:.6f} exceeds max_spike_rate={args.max_spike_rate}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
