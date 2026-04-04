#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"C102 override timing drift gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(v, field):
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True)
    parser.add_argument("--drift-key", default="timing_drift_ms")
    parser.add_argument("--max-drift-ms", type=float, default=0.0)
    args = parser.parse_args()

    data = json.loads(pathlib.Path(args.payload).read_text())
    if not isinstance(data, dict):
        fail("payload must be object")
    drift = to_float(data.get(args.drift_key), args.drift_key)
    if drift > args.max_drift_ms:
        fail(f"timing_drift_ms={drift}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
