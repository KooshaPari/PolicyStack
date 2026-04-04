#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"B96 signature preflight recovery gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid float for {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--recovery-rate-key", default="recovery_rate")
    parser.add_argument("--min-recovery-rate", type=float, default=1.0)
    args = parser.parse_args()

    try:
        report = json.loads(pathlib.Path(args.report).read_text())
    except Exception as exc:
        fail(f"invalid report json: {exc}")

    rate = to_float(report.get(args.recovery_rate_key), "recovery_rate")
    if rate < args.min_recovery_rate:
        fail(f"recovery_rate={rate}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
