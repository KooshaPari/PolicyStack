#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E195 recert exception budget gate failed: {message}", file=sys.stderr)
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
            fail("invalid recert csv")
        if not rows:
            fail("recert csv must contain at least one row")
        return [dict(row) for row in rows]

    try:
        payload = json.loads(path.read_text())
    except Exception:
        fail("invalid recert json")

    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and payload and all(isinstance(item, dict) for item in payload):
        return list(payload)
    fail("recert payload must be a JSON object or non-empty list of objects")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recert", required=True)
    parser.add_argument("--exception-budget-spent-field", default="exception_budget_spent")
    parser.add_argument("--max-exception-budget-spent", type=float, default=1.0)
    parser.add_argument("--over-exception-budget-count-field", default="over_exception_budget_count")
    parser.add_argument("--max-over-exception-budget-count", type=int, default=0)
    args = parser.parse_args()

    records = load_records(pathlib.Path(args.recert))
    for index, record in enumerate(records):
        exception_budget_spent = to_float(
            record.get(args.exception_budget_spent_field),
            args.exception_budget_spent_field,
            index,
        )
        if exception_budget_spent > args.max_exception_budget_spent:
            fail(
                f"{args.exception_budget_spent_field}={exception_budget_spent} > "
                f"{args.max_exception_budget_spent} at index {index}"
            )

        over_exception_budget_count = to_int(
            record.get(args.over_exception_budget_count_field),
            args.over_exception_budget_count_field,
            index,
        )
        if over_exception_budget_count > args.max_over_exception_budget_count:
            fail(
                f"{args.over_exception_budget_count_field}="
                f"{over_exception_budget_count} > "
                f"{args.max_over_exception_budget_count} at index {index}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
