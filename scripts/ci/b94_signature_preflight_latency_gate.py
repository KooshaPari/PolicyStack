#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"B94 signature preflight latency gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid float for {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True)
    parser.add_argument("--latency-key", default="preflight_p95_ms")
    parser.add_argument("--max-p95-ms", type=float, default=0.0)
    args = parser.parse_args()

    try:
        stats = json.loads(pathlib.Path(args.payload).read_text())
    except Exception as exc:
        fail(f"invalid payload: {exc}")

    latency = parse_float(stats.get(args.latency_key), "p95")
    if latency > args.max_p95_ms:
        fail(f"p95_ms={latency}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
