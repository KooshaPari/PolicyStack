#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"C104 replay integrity budget gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(v, field):
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--max-bad-bytes", type=float, default=0.0)
    args = parser.parse_args()

    payload = json.loads(pathlib.Path(args.snapshot).read_text())
    if not isinstance(payload, dict):
        fail("snapshot must be JSON object")

    bad_ratio = to_float(payload.get("integrity_bad_ratio"), "integrity_bad_ratio")
    if bad_ratio > args.max_bad_bytes:
        fail(f"integrity_bad_ratio={bad_ratio}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
