#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"B115 capa reclaim capacity gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--capacity-json", required=True)
    parser.add_argument("--reclaimed-key", default="reclaimed")
    parser.add_argument("--requested-key", default="requested")
    parser.add_argument("--min-reclaim-ratio", type=float, default=0.0)
    parser.add_argument("--max-timeout-ms", type=float, default=0.0)
    parser.add_argument("--timeout-key", default="recovery_ms")
    args = parser.parse_args()

    try:
        payload = json.loads(pathlib.Path(args.capacity_json).read_text())
    except Exception as exc:
        fail(f"invalid capacity json: {exc}")

    if not isinstance(payload, dict):
        fail("capacity-json must be a JSON object")

    reclaimed = parse_float(payload.get(args.reclaimed_key), args.reclaimed_key)
    requested = parse_float(payload.get(args.requested_key), args.requested_key)
    if requested <= 0:
        fail(f"requested={requested} must be > 0")

    ratio = reclaimed / requested
    if ratio < args.min_reclaim_ratio:
        fail(f"reclaim_ratio={ratio} < min_reclaim_ratio={args.min_reclaim_ratio}")

    recovery_ms = parse_int(payload.get(args.timeout_key), args.timeout_key)
    if args.max_timeout_ms and recovery_ms > args.max_timeout_ms:
        fail(f"recovery_ms={recovery_ms} > max_timeout_ms={args.max_timeout_ms}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
