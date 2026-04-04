#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
from typing import Any


def fail(message: str) -> None:
    print(f"E242 federation gap budget gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--federation-gap-budget-report", required=True)
    parser.add_argument("--max-federation-gap", type=float, default=0.0)
    parser.add_argument("--min-federation-gap-pass-rate", type=float, default=0.98)
    parser.add_argument("--max-federation-gap-breach-count", type=int, default=0)
    args = parser.parse_args()

    payload = load_report(pathlib.Path(args.federation_gap_budget_report))
    rows = extract_rows(payload, "federation_gap_budget")

    max_federation_gap = 0.0
    federation_gap_pass_rate = 1.0
    federation_gap_breach_count = 0

    for row in rows:
        max_federation_gap = max(
            max_federation_gap,
            parse_float(
                row.get(
                    "federation_gap",
                    row.get("gap", row.get("gap_seconds", 0.0)),
                ),
                "federation_gap",
            ),
        )
        federation_gap_pass_rate = min(
            federation_gap_pass_rate,
            parse_float(
                row.get(
                    "federation_gap_pass_rate",
                    row.get("gap_pass_rate", row.get("pass_rate", 1.0)),
                ),
                "federation_gap_pass_rate",
            ),
        )
        federation_gap_breach_count += parse_int(
            row.get("federation_gap_breach_count", row.get("gap_breach_count", 0)),
            "federation_gap_breach_count",
        )

    if (
        max_federation_gap > args.max_federation_gap
        or federation_gap_pass_rate < args.min_federation_gap_pass_rate
        or federation_gap_breach_count > args.max_federation_gap_breach_count
    ):
        fail("thresholds exceeded")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
