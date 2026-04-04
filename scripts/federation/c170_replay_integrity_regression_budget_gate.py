#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E170 C170 replay integrity regression stability gate failed: {message}",
        file=sys.stderr,
    )
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
    parser.add_argument("--allowed-regression-delta", type=float, default=0.0)
    parser.add_argument("--min-stability", type=float, default=1.0)
    parser.add_argument("--max-breaches", type=int, default=0)
    parser.add_argument("--max-breach-rate", type=float, default=0.0)
    args = parser.parse_args()

    rows = load_rows(args.replays, ("replays", "runs", "integrity"))
    total = 0
    breaches = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        age = to_int(
            row.get(
                "age_hours",
                row.get("replay_age_hours", row.get("created_in_hours", 0)),
            ),
            "age_hours",
        )
        if age > args.window_hours:
            continue
        total += 1
        baseline = to_float(
            row.get(
                "replay_integrity_baseline_score",
                row.get("integrity_baseline_score", row.get("baseline_score", 0.0)),
            ),
            "replay_integrity_baseline_score",
        )
        current = to_float(
            row.get(
                "replay_integrity_score",
                row.get("integrity_score", row.get("score", baseline)),
            ),
            "replay_integrity_score",
        )
        stability = to_float(
            row.get(
                "replay_integrity_stability",
                row.get("integrity_stability", row.get("stability", 1.0)),
            ),
            "replay_integrity_stability",
        )
        stable = to_bool(
            row.get(
                "stable",
                row.get("replay_integrity_stable", row.get("integrity_stable", True)),
            )
        )
        regression = to_bool(
            row.get(
                "regression",
                row.get(
                    "replay_integrity_regression",
                    row.get("integrity_regression", False),
                ),
            )
        ) or (baseline - current > args.allowed_regression_delta)
        if regression or (not stable) or stability < args.min_stability:
            breaches += 1

    if total == 0:
        fail("no replay entries found")
    breach_rate = breaches / total
    if args.max_breaches and breaches > args.max_breaches:
        fail(f"breaches={breaches}")
    if args.max_breach_rate and breach_rate > to_float(args.max_breach_rate, "max_breach_rate"):
        fail(f"breach_rate={breach_rate:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
