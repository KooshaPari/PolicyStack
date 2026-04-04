#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
from typing import Any


def fail(message: str) -> None:
    print(f"E151 revocation velocity budget gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--revocation-velocity-budget-report", required=True)
    parser.add_argument("--max-revocation-velocity", type=float, default=1.0)
    parser.add_argument("--min-revocation-velocity-pass-rate", type=float, default=0.97)
    parser.add_argument("--max-revocation-velocity-breach-count", type=int, default=0)
    args = parser.parse_args()

    payload = load_report(pathlib.Path(args.revocation_velocity_budget_report))
    rows = extract_rows(payload, "revocation_velocity_budget")

    max_revocation_velocity = 0.0
    revocation_velocity_pass_rate = 1.0
    revocation_velocity_breach_count = 0

    for row in rows:
        max_revocation_velocity = max(
            max_revocation_velocity,
            parse_float(
                row.get(
                    "revocation_velocity",
                    row.get("velocity", row.get("revocations_per_hour", 0.0)),
                ),
                "revocation_velocity",
            ),
        )
        revocation_velocity_pass_rate = min(
            revocation_velocity_pass_rate,
            parse_float(
                row.get(
                    "revocation_velocity_pass_rate",
                    row.get("velocity_pass_rate", row.get("pass_rate", 1.0)),
                ),
                "revocation_velocity_pass_rate",
            ),
        )
        revocation_velocity_breach_count += parse_int(
            row.get(
                "revocation_velocity_breach_count",
                row.get("velocity_breach_count", 0),
            ),
            "revocation_velocity_breach_count",
        )

    if (
        max_revocation_velocity > args.max_revocation_velocity
        or revocation_velocity_pass_rate < args.min_revocation_velocity_pass_rate
        or revocation_velocity_breach_count > args.max_revocation_velocity_breach_count
    ):
        fail("thresholds exceeded")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
