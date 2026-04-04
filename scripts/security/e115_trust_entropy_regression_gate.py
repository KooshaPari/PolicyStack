#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E115 trust entropy regression gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(value: object, field: str) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {value!r}")


def load_rows(path: pathlib.Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        return list(csv.DictReader(path.read_text().splitlines()))
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("attestations", "records", "items", "entries"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
    fail("attestations payload must be list or object with attestations/records/items/entries")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attestations", required=True)
    parser.add_argument("--entropy-col", default="entropy")
    parser.add_argument("--max-avg-entropy", type=float, default=1.0)
    parser.add_argument("--max-spike-count", type=int, default=0)
    parser.add_argument("--spike-threshold", type=float, default=2.0)
    args = parser.parse_args()

    rows = load_rows(pathlib.Path(args.attestations))
    if not rows:
        fail("attestations payload must contain rows")

    entropies = [parse_float(row.get(args.entropy_col), args.entropy_col) for row in rows]
    avg_entropy = sum(entropies) / len(entropies)
    spike_count = sum(1 for entropy in entropies if entropy > args.spike_threshold)

    if avg_entropy > args.max_avg_entropy:
        fail(f"avg_entropy={avg_entropy}")
    if spike_count > args.max_spike_count:
        fail(f"spike_count={spike_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
