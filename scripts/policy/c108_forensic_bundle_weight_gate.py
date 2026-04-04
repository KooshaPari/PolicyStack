#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"C108 forensic bundle weight gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_int(v, field):
    try:
        return int(v)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {v!r}")


def to_float(v, field):
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--max-bundle-size", type=int, default=0)
    parser.add_argument("--max-null-fields", type=int, default=0)
    parser.add_argument("--max-weight", type=float, default=1.0)
    args = parser.parse_args()

    payload = json.loads(pathlib.Path(args.snapshot).read_text())
    if not isinstance(payload, dict):
        fail("snapshot must be JSON object")

    size = to_int(payload.get("bundle_size", 0), "bundle_size")
    null_fields = to_int(payload.get("null_fields", 0), "null_fields")
    weight = to_float(payload.get("risk_weight", 0.0), "risk_weight")

    if size > args.max_bundle_size:
        fail(f"bundle_size={size}")

    if null_fields > args.max_null_fields:
        fail(f"null_fields={null_fields}")

    if weight > args.max_weight:
        fail(f"risk_weight={weight}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
