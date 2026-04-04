#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"B111 attestation SLI gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--stats", required=True)
    parser.add_argument("--error-rate-key", default="error_rate")
    parser.add_argument("--max-error-rate", type=float, default=1.0)
    parser.add_argument("--burn-rate-key", default="burn_rate")
    parser.add_argument("--max-burn-rate", type=float, default=1.0)
    parser.add_argument("--incident-count-key", default="incidents")
    parser.add_argument("--max-incidents", type=int, default=0)
    args = parser.parse_args()

    try:
        payload = json.loads(pathlib.Path(args.stats).read_text())
    except Exception as exc:
        fail(f"invalid stats json: {exc}")
    if not isinstance(payload, dict):
        fail("stats must be a JSON object")

    error_rate = parse_float(payload.get(args.error_rate_key), args.error_rate_key)
    if not (0.0 <= error_rate <= 1.0):
        fail(f"error_rate must be a ratio between 0 and 1: {error_rate}")
    if error_rate > args.max_error_rate:
        fail(f"error_rate={error_rate} > max={args.max_error_rate}")

    burn_rate = parse_float(payload.get(args.burn_rate_key), args.burn_rate_key)
    if burn_rate > args.max_burn_rate:
        fail(f"burn_rate={burn_rate} > max={args.max_burn_rate}")

    incidents = parse_int(payload.get(args.incident_count_key), args.incident_count_key)
    if incidents > args.max_incidents:
        fail(f"incidents={incidents} > max={args.max_incidents}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
