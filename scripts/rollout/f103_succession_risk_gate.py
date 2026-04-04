#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"F103 succession risk gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(v, field):
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--succession-csv", required=True)
    parser.add_argument("--risk-col", default="risk_score")
    parser.add_argument("--max-risk", type=float, default=1.0)
    args = parser.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.succession_csv).read_text().splitlines()))
    if not rows:
        fail("no succession rows")

    high = [r for r in rows if to_float(r.get(args.risk_col), args.risk_col) > args.max_risk]
    if high:
        fail(f"high_risk_roles={len(high)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
