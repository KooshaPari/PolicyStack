#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E205 C205 forensic window stability budget gate failed: {message}",
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
    parser.add_argument("--forensics", required=True)
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument("--min-stability", type=float, default=1.0)
    parser.add_argument("--allowed-budget-overrun", type=float, default=0.0)
    parser.add_argument("--max-breaches", type=int, default=0)
    parser.add_argument("--max-breach-rate", type=float, default=0.0)
    args = parser.parse_args()

    rows = load_rows(args.forensics, ("forensics", "windows", "window", "bundles"))
    total = 0
    breaches = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        age = to_int(
            row.get(
                "age_hours",
                row.get("forensic_age_hours", row.get("window_age_hours", 0)),
            ),
            "age_hours",
        )
        if age > args.window_hours:
            continue
        total += 1
        stability = to_float(
            row.get(
                "forensic_window_stability",
                row.get(
                    "window_stability",
                    row.get(
                        "forensic_stability",
                        row.get("stability", 1.0),
                    ),
                ),
            ),
            "forensic_window_stability",
        )
        stable = to_bool(
            row.get(
                "stable",
                row.get("window_stable", row.get("forensic_stable", True)),
            )
        )
        budget = to_float(
            row.get(
                "forensic_window_budget",
                row.get("window_budget", row.get("forensic_budget", row.get("budget", 0.0))),
            ),
            "forensic_window_budget",
        )
        actual = to_float(
            row.get(
                "forensic_window_cost",
                row.get(
                    "window_cost",
                    row.get(
                        "forensic_cost",
                        row.get("cost", budget),
                    ),
                ),
            ),
            "forensic_window_cost",
        )
        if (not stable) or stability < args.min_stability:
            breaches += 1
            continue
        budget_breach = to_bool(
            row.get(
                "budget_breach",
                row.get(
                    "forensic_window_budget_breach",
                    row.get(
                        "window_budget_breach",
                        row.get("forensic_budget_breach", row.get("budget_breach_count", False)),
                    ),
                ),
            )
        )
        if budget_breach or (actual - budget > args.allowed_budget_overrun):
            breaches += 1

    if total == 0:
        fail("no forensic entries found in window")
    breach_rate = breaches / total
    if args.max_breaches and breaches > args.max_breaches:
        fail(f"breaches={breaches}")
    if args.max_breach_rate and breach_rate > to_float(args.max_breach_rate, "max_breach_rate"):
        fail(f"breach_rate={breach_rate:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
