#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E119 C119 override activity burst gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--overrides", required=True)
    parser.add_argument("--burst-window-hours", type=int, default=1)
    parser.add_argument("--max-burst-activity", type=int, default=0)
    parser.add_argument("--max-burst-rate", type=float, default=0.0)
    args = parser.parse_args()

    rows = load_rows(args.overrides, ("overrides", "activity", "events"))
    total = 0
    burst = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        total += 1
        age = to_int(row.get("created_in_hours", row.get("age_hours", 999999)), "created_in_hours")
        state = str(row.get("state", "")).strip().lower()
        if state == "active" and age <= args.burst_window_hours:
            burst += 1

    if total == 0:
        fail("no override entries found")
    burst_rate = burst / total
    if args.max_burst_activity and burst > args.max_burst_activity:
        fail(f"burst_activity={burst}")
    if args.max_burst_rate and burst_rate > to_float(args.max_burst_rate, "max_burst_rate"):
        fail(f"burst_rate={burst_rate:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
