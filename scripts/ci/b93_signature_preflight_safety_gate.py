#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"B93 signature preflight safety gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid float for {field}: {value!r}")


def parse_int(value, field):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        fail(f"invalid int for {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True)
    parser.add_argument("--safety-score-key", default="preflight_safety_score")
    parser.add_argument("--failure-count-key", default="preflight_failures")
    parser.add_argument("--max-safety-score", type=float, default=0.0)
    parser.add_argument("--max-failures", type=int, default=0)
    args = parser.parse_args()

    try:
        stats = json.loads(pathlib.Path(args.payload).read_text())
    except Exception as exc:
        fail(f"invalid payload: {exc}")
    if not isinstance(stats, dict):
        fail("payload must be JSON object")

    safety = parse_float(stats.get(args.safety_score_key), "safety_score")
    failures = parse_int(stats.get(args.failure_count_key), "failure_count")

    if safety < args.max_safety_score or failures > args.max_failures:
        fail(f"safety_score={safety} failures={failures}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
