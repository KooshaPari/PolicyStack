#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E120 succession stability gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(value: object, field: str, index: int) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid float in {field} at index {index}: {value!r}")


def to_int(value: object, field: str, index: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"invalid int in {field} at index {index}: {value!r}")


def load_records(path: pathlib.Path) -> list[dict[str, object]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        except Exception:
            fail("invalid succession csv")
        if not rows:
            fail("succession csv must contain at least one row")
        return [dict(row) for row in rows]

    try:
        payload = json.loads(path.read_text())
    except Exception:
        fail("invalid succession json")

    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and payload and all(isinstance(item, dict) for item in payload):
        return list(payload)
    fail("succession payload must be a JSON object or non-empty list of objects")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--succession", required=True)
    parser.add_argument("--stability-score-field", default="stability_score")
    parser.add_argument("--min-stability-score", type=float, default=0.85)
    parser.add_argument("--handoff-failures-field", default="handoff_failure_count")
    parser.add_argument("--max-handoff-failures", type=int, default=0)
    args = parser.parse_args()

    records = load_records(pathlib.Path(args.succession))
    for index, record in enumerate(records):
        stability = to_float(record.get(args.stability_score_field), args.stability_score_field, index)
        if stability < args.min_stability_score:
            fail(
                f"{args.stability_score_field}={stability} < "
                f"{args.min_stability_score} at index {index}"
            )

        failures = to_int(record.get(args.handoff_failures_field), args.handoff_failures_field, index)
        if failures > args.max_handoff_failures:
            fail(
                f"{args.handoff_failures_field}={failures} > "
                f"{args.max_handoff_failures} at index {index}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
