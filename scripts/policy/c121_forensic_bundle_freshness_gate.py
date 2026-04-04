#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E121 C121 forensic bundle freshness gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_int(v, field: str) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {v!r}")


def to_float(v, field: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def load_rows(path: str, keys: tuple[str, ...]) -> list[dict]:
    p = pathlib.Path(path)
    if p.suffix.lower() == ".csv":
        return list(csv.DictReader(p.read_text().splitlines()))
    payload = json.loads(p.read_text())
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            rows = payload.get(key)
            if isinstance(rows, list):
                return rows
        if payload and all(isinstance(v, dict) for v in payload.values()):
            return list(payload.values())
    fail("input must be CSV rows or JSON list/object with known keys")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forensics", required=True)
    parser.add_argument("--freshness-sla-hours", type=int, default=24)
    parser.add_argument("--max-stale-bundles", type=int, default=0)
    parser.add_argument("--max-stale-rate", type=float, default=0.0)
    args = parser.parse_args()

    rows = load_rows(args.forensics, ("forensics", "bundles", "alerts"))
    total = 0
    stale = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        total += 1
        age = to_int(row.get("age_hours", row.get("bundle_age_hours", 0)), "age_hours")
        if age > args.freshness_sla_hours:
            stale += 1

    if total == 0:
        fail("no forensic entries found")
    stale_rate = stale / total
    if args.max_stale_bundles and stale > args.max_stale_bundles:
        fail(f"stale_bundles={stale}")
    if args.max_stale_rate and stale_rate > to_float(args.max_stale_rate, "max_stale_rate"):
        fail(f"stale_rate={stale_rate:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
