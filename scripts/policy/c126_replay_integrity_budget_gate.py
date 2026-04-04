#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E126 C126 replay integrity budget gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--replays", required=True)
    parser.add_argument("--integrity-budget", type=float, default=0.0)
    parser.add_argument("--max-budget-breaches", type=int, default=0)
    parser.add_argument("--max-budget-breach-rate", type=float, default=0.0)
    args = parser.parse_args()

    rows = load_rows(args.replays, ("replays", "runs", "integrity"))
    total = 0
    breaches = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        total += 1
        spent = to_float(
            row.get("integrity_spend", row.get("integrity_cost", row.get("budget_spend", 0.0))),
            "integrity_spend",
        )
        violations = to_int(
            row.get("integrity_violations", row.get("violation_count", 0)), "integrity_violations"
        )
        effective_spend = spent + float(violations)
        if args.integrity_budget and effective_spend > args.integrity_budget:
            breaches += 1

    if total == 0:
        fail("no replay entries found")
    breach_rate = breaches / total
    if args.max_budget_breaches and breaches > args.max_budget_breaches:
        fail(f"budget_breaches={breaches}")
    if args.max_budget_breach_rate and breach_rate > to_float(
        args.max_budget_breach_rate, "max_budget_breach_rate"
    ):
        fail(f"budget_breach_rate={breach_rate:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
