#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E118 C118 replay integrity regression gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(v, field: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y", "ok", "pass"}


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
    parser.add_argument("--max-regressions", type=int, default=0)
    parser.add_argument("--max-regression-rate", type=float, default=0.0)
    args = parser.parse_args()

    rows = load_rows(args.replays, ("replays", "runs", "integrity"))
    total = 0
    regressions = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        total += 1
        status = str(row.get("status", "")).strip().lower()
        integrity_ok = to_bool(row.get("integrity_ok", row.get("checksum_match", True)))
        if status in {"failed", "error", "fatal"} or not integrity_ok:
            regressions += 1

    if total == 0:
        fail("no replay entries found")
    regression_rate = regressions / total
    if args.max_regressions and regressions > args.max_regressions:
        fail(f"regressions={regressions}")
    if args.max_regression_rate and regression_rate > to_float(args.max_regression_rate, "max_rate"):
        fail(f"regression_rate={regression_rate:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
