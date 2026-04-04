#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E126 kpi stability budget gate failed: {message}", file=sys.stderr)
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
            fail("invalid kpi csv")
        if not rows:
            fail("kpi csv must contain at least one row")
        return [dict(row) for row in rows]

    try:
        payload = json.loads(path.read_text())
    except Exception:
        fail("invalid kpi json")

    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and payload and all(isinstance(item, dict) for item in payload):
        return list(payload)
    fail("kpi payload must be a JSON object or non-empty list of objects")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kpi", required=True)
    parser.add_argument("--stability-budget-spent-field", default="stability_budget_spent")
    parser.add_argument("--max-stability-budget-spent", type=float, default=1.0)
    parser.add_argument("--over-budget-kpi-count-field", default="over_budget_kpi_count")
    parser.add_argument("--max-over-budget-kpi-count", type=int, default=0)
    args = parser.parse_args()

    records = load_records(pathlib.Path(args.kpi))
    for index, record in enumerate(records):
        stability_budget_spent = to_float(
            record.get(args.stability_budget_spent_field), args.stability_budget_spent_field, index
        )
        if stability_budget_spent > args.max_stability_budget_spent:
            fail(
                f"{args.stability_budget_spent_field}={stability_budget_spent} > "
                f"{args.max_stability_budget_spent} at index {index}"
            )

        over_budget_kpi_count = to_int(
            record.get(args.over_budget_kpi_count_field), args.over_budget_kpi_count_field, index
        )
        if over_budget_kpi_count > args.max_over_budget_kpi_count:
            fail(
                f"{args.over_budget_kpi_count_field}={over_budget_kpi_count} > "
                f"{args.max_over_budget_kpi_count} at index {index}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
