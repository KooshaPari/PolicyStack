#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E216 C216 playbook guardrail budget gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y", "ok", "pass"}


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
    parser.add_argument("--playbook", required=True)
    parser.add_argument("--allowed-budget-overrun", type=float, default=0.0)
    parser.add_argument("--max-budget-breaches", type=int, default=0)
    parser.add_argument("--max-budget-breach-rate", type=float, default=0.0)
    args = parser.parse_args()

    rows = load_rows(args.playbook, ("steps", "playbook", "guardrails"))
    total = 0
    breaches = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        total += 1
        budget = to_float(
            row.get(
                "playbook_guardrail_budget",
                row.get("guardrail_budget", row.get("budget", 0.0)),
            ),
            "playbook_guardrail_budget",
        )
        actual = to_float(
            row.get(
                "playbook_guardrail_cost",
                row.get("guardrail_cost", row.get("cost", budget)),
            ),
            "playbook_guardrail_cost",
        )
        budget_breach = to_bool(
            row.get(
                "budget_breach",
                row.get(
                    "playbook_guardrail_budget_breach",
                    row.get("guardrail_budget_breach", False),
                ),
            )
        )
        if budget_breach or (actual - budget > args.allowed_budget_overrun):
            breaches += 1

    if total == 0:
        fail("no playbook entries found")
    breach_rate = breaches / total
    if args.max_budget_breaches and breaches > args.max_budget_breaches:
        fail(f"budget_breaches={breaches}")
    if (
        args.max_budget_breach_rate
        and breach_rate > to_float(args.max_budget_breach_rate, "max_budget_breach_rate")
    ):
        fail(f"budget_breach_rate={breach_rate:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
