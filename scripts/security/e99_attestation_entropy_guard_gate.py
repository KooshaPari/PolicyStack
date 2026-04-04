#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E99 attestation entropy guard gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(v, field):
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attestations", required=True)
    parser.add_argument("--entropy-key", default="entropy")
    parser.add_argument("--min-entropy", type=float, default=0.0)
    args = parser.parse_args()

    data = json.loads(pathlib.Path(args.attestations).read_text())
    if isinstance(data, dict):
        rows = data.get("items", data.get("attestations", []))
    else:
        rows = data

    if not isinstance(rows, list):
        fail("attestations payload must be list or object with items")

    low = sum(1 for r in rows if to_float(r.get(args.entropy_key), args.entropy_key) < args.min_entropy)
    if low:
        fail(f"low_entropy_count={low}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
