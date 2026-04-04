#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E129 C129 forensic bundle window gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument("--max-window-missing", type=int, default=0)
    parser.add_argument("--max-window-missing-rate", type=float, default=0.0)
    args = parser.parse_args()

    rows = load_rows(args.forensics, ("forensics", "bundles", "window"))
    total = 0
    missing = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        age = to_int(row.get("age_hours", row.get("window_age_hours", 0)), "age_hours")
        if age > args.window_hours:
            continue
        total += 1
        bundle_count = to_float(
            row.get("bundle_count", row.get("forensic_bundle_count", row.get("count", 0.0))),
            "bundle_count",
        )
        if bundle_count <= 0.0:
            missing += 1

    if total == 0:
        fail("no forensic entries found in window")
    missing_rate = missing / total
    if args.max_window_missing and missing > args.max_window_missing:
        fail(f"window_missing={missing}")
    if args.max_window_missing_rate and missing_rate > to_float(
        args.max_window_missing_rate, "max_window_missing_rate"
    ):
        fail(f"window_missing_rate={missing_rate:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
