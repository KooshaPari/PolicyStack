#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E144 C144 playbook guardrail regression budget gate failed: {message}",
        file=sys.stderr,
    )
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
    parser.add_argument("--allowed-regression-delta", type=float, default=0.0)
    parser.add_argument("--allowed-budget-overrun", type=float, default=0.0)
    parser.add_argument("--max-breaches", type=int, default=0)
    parser.add_argument("--max-breach-rate", type=float, default=0.0)
    args = parser.parse_args()

    rows = load_rows(args.playbook, ("steps", "playbook", "guardrails"))
    total = 0
    breaches = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        total += 1
        baseline = to_float(
            row.get(
                "playbook_guardrail_baseline_score",
                row.get("guardrail_baseline_score", row.get("baseline_score", 0.0)),
            ),
            "playbook_guardrail_baseline_score",
        )
        current = to_float(
            row.get(
                "playbook_guardrail_score",
                row.get("guardrail_score", row.get("score", baseline)),
            ),
            "playbook_guardrail_score",
        )
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
        regression = to_bool(
            row.get("regression", row.get("playbook_guardrail_regression", False))
        ) or (baseline - current > args.allowed_regression_delta)
        budget_breach = to_bool(
            row.get(
                "budget_breach",
                row.get("playbook_guardrail_budget_breach", row.get("guardrail_budget_breach", False)),
            )
        ) or (actual - budget > args.allowed_budget_overrun)
        if regression or budget_breach:
            breaches += 1

    if total == 0:
        fail("no playbook entries found")
    breach_rate = breaches / total
    if args.max_breaches and breaches > args.max_breaches:
        fail(f"breaches={breaches}")
    if args.max_breach_rate and breach_rate > to_float(args.max_breach_rate, "max_breach_rate"):
        fail(f"breach_rate={breach_rate:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
