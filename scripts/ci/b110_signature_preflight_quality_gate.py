#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"B110 signature preflight quality gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid numeric value for {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True)
    parser.add_argument("--quality-key", default="quality_score")
    parser.add_argument("--min-quality", type=float, default=0.0)
    parser.add_argument("--timeout-key", default="p95_latency_ms")
    parser.add_argument("--max-timeout-ms", type=float, default=0.0)
    args = parser.parse_args()

    try:
        payload = json.loads(pathlib.Path(args.payload).read_text())
    except Exception as exc:
        fail(f"invalid payload json: {exc}")

    if not isinstance(payload, dict):
        fail("payload must be a JSON object")

    quality = parse_float(payload.get(args.quality_key), args.quality_key)
    if quality < args.min_quality:
        fail(f"quality_score={quality} < min={args.min_quality}")

    timeout = parse_float(payload.get(args.timeout_key), args.timeout_key)
    if timeout > args.max_timeout_ms:
        fail(f"p95_latency_ms={timeout} > max={args.max_timeout_ms}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
