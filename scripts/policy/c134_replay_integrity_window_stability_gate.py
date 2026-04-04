#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E134 C134 replay integrity window stability gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y", "ok", "pass"}


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
    parser.add_argument("--replays", required=True)
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument("--min-window-stability", type=float, default=1.0)
    parser.add_argument("--max-unstable", type=int, default=0)
    parser.add_argument("--max-unstable-rate", type=float, default=0.0)
    args = parser.parse_args()

    rows = load_rows(args.replays, ("replays", "runs", "integrity"))
    total = 0
    unstable = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        age = to_int(row.get("age_hours", row.get("replay_age_hours", 0)), "age_hours")
        if age > args.window_hours:
            continue
        total += 1
        stability = to_float(
            row.get(
                "integrity_window_stability",
                row.get("window_stability", row.get("replay_stability", 1.0)),
            ),
            "integrity_window_stability",
        )
        stable = to_bool(row.get("stable", row.get("integrity_stable", True)))
        if (not stable) or stability < args.min_window_stability:
            unstable += 1

    if total == 0:
        fail("no replay entries found in window")
    unstable_rate = unstable / total
    if args.max_unstable and unstable > args.max_unstable:
        fail(f"window_unstable={unstable}")
    if args.max_unstable_rate and unstable_rate > to_float(args.max_unstable_rate, "max_unstable_rate"):
        fail(f"window_unstable_rate={unstable_rate:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
