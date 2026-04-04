#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"C103 playbook stability margin gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(v, field):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def to_int(v, field):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playbooks-csv", required=True)
    parser.add_argument("--min-stability-margin", type=float, default=0.0)
    parser.add_argument("--max-violations", type=int, default=0)
    args = parser.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.playbooks_csv).read_text().splitlines()))
    violations = 0
    for row in rows:
        score = to_float(row.get("stability_margin", "0.0"), "stability_margin")
        if score < args.min_stability_margin:
            violations += 1
    if violations > args.max_violations:
        fail(f"stability_violations={violations}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
