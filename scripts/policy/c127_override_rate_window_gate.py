#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E127 C127 override rate window gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument("--max-window-rate", type=float, default=0.0)
    parser.add_argument("--max-window-rate-breaches", type=int, default=0)
    parser.add_argument("--max-window-breach-rate", type=float, default=0.0)
    args = parser.parse_args()

    rows = load_rows(args.overrides, ("overrides", "activity", "rates"))
    total = 0
    breaches = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        age = to_int(row.get("age_hours", row.get("window_age_hours", 0)), "age_hours")
        if age > args.window_hours:
            continue
        total += 1
        override_rate = to_float(
            row.get("override_rate", row.get("window_rate", row.get("rate", 0.0))), "override_rate"
        )
        if args.max_window_rate and override_rate > args.max_window_rate:
            breaches += 1

    if total == 0:
        fail("no override entries found in window")
    breach_rate = breaches / total
    if args.max_window_rate_breaches and breaches > args.max_window_rate_breaches:
        fail(f"window_rate_breaches={breaches}")
    if args.max_window_breach_rate and breach_rate > to_float(
        args.max_window_breach_rate, "max_window_breach_rate"
    ):
        fail(f"window_breach_rate={breach_rate:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
