#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"B116 signature preflight entropy gate failed: {message}", file=sys.stderr)
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True)
    parser.add_argument("--entropy-key", default="entropy")
    parser.add_argument("--min-entropy", type=float, default=0.0)
    parser.add_argument("--unique-key", default="unique_signatures")
    parser.add_argument("--min-unique-ratio", type=float, default=0.0)
    parser.add_argument("--total-key", default="sample_count")
    args = parser.parse_args()

    try:
        payload = json.loads(pathlib.Path(args.payload).read_text())
    except Exception as exc:
        fail(f"invalid payload json: {exc}")

    if not isinstance(payload, dict):
        fail("payload must be a JSON object")

    entropy = parse_float(payload.get(args.entropy_key), args.entropy_key)
    if entropy < args.min_entropy:
        fail(f"entropy={entropy} < min_entropy={args.min_entropy}")

    total = parse_int(payload.get(args.total_key), args.total_key)
    unique = parse_int(payload.get(args.unique_key), args.unique_key)
    if total <= 0:
        fail(f"total_signatures={total} must be > 0")

    unique_ratio = unique / total
    if unique_ratio < args.min_unique_ratio:
        fail(f"unique_ratio={unique_ratio} < min_unique_ratio={args.min_unique_ratio}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
