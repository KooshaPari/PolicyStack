#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"C110 override toxicity gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(v, field):
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def to_int(v, field):
    try:
        return int(v)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {v!r}")


def row_is_active(row: dict) -> bool:
    return str(row.get("active", "true")).strip().lower() in {"1", "true", "yes", "y"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overrides", required=True)
    parser.add_argument("--max-active-overrides", type=int, default=0)
    parser.add_argument("--max-high-risk-overrides", type=int, default=0)
    parser.add_argument("--max-risk-score", type=float, default=0.8)
    args = parser.parse_args()

    payload = json.loads(pathlib.Path(args.overrides).read_text())
    rows = payload.get("overrides", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        fail("overrides JSON must be a list or contain overrides")

    active_count = 0
    high_risk = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not row_is_active(row):
            continue
        active_count += 1

        risk = to_float(row.get("risk_score", 0.0), "risk_score")
        if risk > args.max_risk_score:
            high_risk += 1

    if args.max_active_overrides and active_count > args.max_active_overrides:
        fail(f"active_overrides={active_count}")

    if high_risk > args.max_high_risk_overrides:
        fail(f"high_risk_overrides={high_risk}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
