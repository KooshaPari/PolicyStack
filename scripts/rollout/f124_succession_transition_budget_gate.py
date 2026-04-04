#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E124 succession transition budget gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--transition-budget-spent-field", default="transition_budget_spent")
    parser.add_argument("--max-transition-budget-spent", type=float, default=1.0)
    parser.add_argument("--over-budget-transitions-field", default="over_budget_transition_count")
    parser.add_argument("--max-over-budget-transitions", type=int, default=0)
    args = parser.parse_args()

    records = load_records(pathlib.Path(args.succession))
    for index, record in enumerate(records):
        budget_spent = to_float(
            record.get(args.transition_budget_spent_field), args.transition_budget_spent_field, index
        )
        if budget_spent > args.max_transition_budget_spent:
            fail(
                f"{args.transition_budget_spent_field}={budget_spent} > "
                f"{args.max_transition_budget_spent} at index {index}"
            )

        over_budget_transitions = to_int(
            record.get(args.over_budget_transitions_field), args.over_budget_transitions_field, index
        )
        if over_budget_transitions > args.max_over_budget_transitions:
            fail(
                f"{args.over_budget_transitions_field}={over_budget_transitions} > "
                f"{args.max_over_budget_transitions} at index {index}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
