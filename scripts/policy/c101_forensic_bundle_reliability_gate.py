#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"C101 forensic bundle reliability gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--reliability-csv", required=True)
    parser.add_argument("--max-low-reliability", type=int, default=0)
    parser.add_argument("--max-failing-ratio", type=float, default=0.0)
    args = parser.parse_args()

    try:
        bundle = json.loads(pathlib.Path(args.bundle).read_text())
    except Exception as exc:
        fail(f"invalid bundle JSON: {exc}")
    rows = list(csv.DictReader(pathlib.Path(args.reliability_csv).read_text().splitlines()))

    total = len(rows)
    low = sum(1 for r in rows if num(r.get("reliability", 1.0)) < args.max_failing_ratio)
    if total > 0 and low > args.max_low_reliability:
        fail(f"low_reliability={low}")
    ratio = low / max(total, 1)
    if ratio > args.max_failing_ratio:
        fail(f"low_reliability_ratio={ratio}")

    if not isinstance(bundle, dict) or bundle.get("bundle_verified") is not True:
        fail("bundle_verified != true")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
