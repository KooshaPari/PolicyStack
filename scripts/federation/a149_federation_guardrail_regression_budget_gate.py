#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
from typing import Any


def fail(message: str) -> None:
    print(f"E149 federation guardrail regression budget gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_report(path: pathlib.Path) -> list[dict[str, Any]] | dict[str, Any]:
    raw = path.read_text()
    if path.suffix.lower() == ".csv":
        return list(csv.DictReader(raw.splitlines()))
    return json.loads(raw)


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
    parser.add_argument("--guardrail-regression-budget-report", required=True)
    parser.add_argument("--max-guardrail-regression-rate", type=float, default=0.02)
    parser.add_argument(
        "--min-guardrail-regression-stability-rate", type=float, default=0.98
    )
    parser.add_argument("--max-guardrail-regression-breach-count", type=int, default=0)
    args = parser.parse_args()

    payload = load_report(pathlib.Path(args.guardrail_regression_budget_report))
    rows = extract_rows(payload, "federation_guardrail_regression_budget")

    max_guardrail_regression_rate = 0.0
    guardrail_regression_stability_rate = 1.0
    guardrail_regression_breach_count = 0

    for row in rows:
        max_guardrail_regression_rate = max(
            max_guardrail_regression_rate,
            parse_float(
                row.get(
                    "guardrail_regression_rate",
                    row.get(
                        "federation_guardrail_regression_rate",
                        row.get("regression_rate", 0.0),
                    ),
                ),
                "guardrail_regression_rate",
            ),
        )
        guardrail_regression_stability_rate = min(
            guardrail_regression_stability_rate,
            parse_float(
                row.get(
                    "guardrail_regression_stability_rate",
                    row.get(
                        "federation_guardrail_regression_stability_rate",
                        row.get("stability_rate", 1.0),
                    ),
                ),
                "guardrail_regression_stability_rate",
            ),
        )
        guardrail_regression_breach_count += parse_int(
            row.get(
                "guardrail_regression_breach_count",
                row.get("regression_breach_count", 0),
            ),
            "guardrail_regression_breach_count",
        )

    if (
        max_guardrail_regression_rate > args.max_guardrail_regression_rate
        or guardrail_regression_stability_rate
        < args.min_guardrail_regression_stability_rate
        or guardrail_regression_breach_count
        > args.max_guardrail_regression_breach_count
    ):
        fail("thresholds exceeded")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
