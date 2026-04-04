#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E106 attestation entropy gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(v, field: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attestations", required=True)
    parser.add_argument("--entropy-col", default="entropy")
    parser.add_argument("--max-avg-entropy", type=float, default=1.0)
    args = parser.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.attestations).read_text().splitlines()))
    if not rows:
        fail("attestations payload must contain rows")

    total_entropy = sum(parse_float(row.get(args.entropy_col), args.entropy_col) for row in rows)
    avg_entropy = total_entropy / len(rows)
    if avg_entropy > args.max_avg_entropy:
        fail(f"avg_entropy={avg_entropy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
