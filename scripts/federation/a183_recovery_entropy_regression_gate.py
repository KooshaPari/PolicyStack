#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
from typing import Any


def fail(message: str) -> None:
    print(f"E183 recovery entropy budget gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_report(path: pathlib.Path) -> list[dict[str, Any]] | dict[str, Any]:
    raw = path.read_text()
    if path.suffix.lower() == ".csv":
        return list(csv.DictReader(raw.splitlines()))
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON report {path}: {exc}")


def extract_rows(
    payload: list[dict[str, Any]] | dict[str, Any], lane_key: str
) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    rows = payload.get("items") or payload.get("records") or payload.get("entries") or payload.get(
        lane_key
    )
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def parse_float(value: object, label: str) -> float:
    try:
        return float(str(value))
    except Exception:
        fail(f"invalid float for {label}: {value!r}")


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        fail(f"invalid integer for {label}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recovery-entropy-budget-report", required=True)
    parser.add_argument("--max-recovery-entropy-over-budget-rate", type=float, default=0.0)
    parser.add_argument("--min-recovery-entropy-stability-rate", type=float, default=0.95)
    parser.add_argument("--max-recovery-entropy-breach-count", type=int, default=0)
    args = parser.parse_args()

    payload = load_report(pathlib.Path(args.recovery_entropy_budget_report))
    rows = extract_rows(payload, "recovery_entropy_budget")

    max_recovery_entropy_over_budget_rate = 0.0
    recovery_entropy_stability_rate = 1.0
    recovery_entropy_breach_count = 0

    for row in rows:
        max_recovery_entropy_over_budget_rate = max(
            max_recovery_entropy_over_budget_rate,
            parse_float(
                row.get(
                    "recovery_entropy_over_budget_rate",
                    row.get(
                        "recovery_entropy_budget_overage_rate",
                        row.get("over_budget_rate", 0.0),
                    ),
                ),
                "recovery_entropy_over_budget_rate",
            ),
        )
        recovery_entropy_stability_rate = min(
            recovery_entropy_stability_rate,
            parse_float(
                row.get(
                    "recovery_entropy_stability_rate",
                    row.get("recovery_entropy_rate", row.get("stability_rate", 1.0)),
                ),
                "recovery_entropy_stability_rate",
            ),
        )
        recovery_entropy_breach_count += parse_int(
            row.get("recovery_entropy_breach_count", row.get("over_budget_count", 0)),
            "recovery_entropy_breach_count",
        )

    if (
        max_recovery_entropy_over_budget_rate > args.max_recovery_entropy_over_budget_rate
        or recovery_entropy_stability_rate < args.min_recovery_entropy_stability_rate
        or recovery_entropy_breach_count > args.max_recovery_entropy_breach_count
    ):
        fail("thresholds exceeded")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
