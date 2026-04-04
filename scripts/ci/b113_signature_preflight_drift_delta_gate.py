#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"B113 signature preflight drift delta gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid numeric value for {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True)
    parser.add_argument("--drift-key", default="drift_percent")
    parser.add_argument("--max-drift", type=float, default=0.0)
    parser.add_argument("--baseline-key", default="baseline_percent")
    parser.add_argument("--max-baseline-delta", type=float, default=0.0)
    args = parser.parse_args()

    try:
        payload = json.loads(pathlib.Path(args.payload).read_text())
    except Exception as exc:
        fail(f"invalid payload json: {exc}")

    if not isinstance(payload, dict):
        fail("payload must be a JSON object")

    drift = parse_float(payload.get(args.drift_key), args.drift_key)
    if abs(drift) > args.max_drift:
        fail(f"drift_percent={drift} exceeds max={args.max_drift}")

    baseline = parse_float(payload.get(args.baseline_key), args.baseline_key)
    delta = abs(drift - baseline)
    if delta > args.max_baseline_delta:
        fail(f"drift_baseline_delta={delta} exceeds max={args.max_baseline_delta}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
