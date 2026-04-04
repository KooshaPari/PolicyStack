#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"A104 chaos evidence tenure gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(value, default=0.0) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--max-missing-tenure", type=float, default=0.0)
    parser.add_argument("--max-expired-tenure-count", type=int, default=0)
    args = parser.parse_args()

    try:
        data = json.loads(pathlib.Path(args.evidence).read_text())
    except Exception as exc:
        fail(f"invalid evidence json: {exc}")

    items = data if isinstance(data, list) else data.get("evidence", []) if isinstance(data, dict) else []
    if not isinstance(items, list):
        fail("evidence payload must be list or object with evidence list")

    missing = 0
    expired_count = 0
    for item in items:
        tenure = to_float(item.get("evidence_tenure_days", 0.0), 0.0)
        if tenure <= 0:
            missing += 1
        if item.get("expired", False):
            expired_count += 1

    if missing > 0 and args.max_missing_tenure >= 0:
        if missing > args.max_missing_tenure:
            fail(f"missing_tenure={missing}")
    if expired_count > args.max_expired_tenure_count:
        fail(f"expired_tenure_count={expired_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
