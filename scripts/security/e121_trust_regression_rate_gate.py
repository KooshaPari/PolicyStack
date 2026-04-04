#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


REGRESSION_STATUSES = {"regression", "degradation", "drop", "error", "fail", "rollback"}


def fail(message: str) -> None:
    print(f"E121 trust regression rate gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(value: object, field: str) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {value!r}")


def load_rows(path: pathlib.Path) -> list[dict]:
    try:
        if path.suffix.lower() == ".csv":
            return list(csv.DictReader(path.read_text().splitlines()))
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid transitions input: {exc}")

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("transitions", "records", "items", "entries", "attestations"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
    fail("transitions payload must be list or object with transitions/records/items/entries/attestations")


def is_regression_row(
    row: dict,
    previous_row: dict | None,
    trust_col: str,
    status_col: str,
    drop_threshold: float,
) -> bool:
    status = str(row.get(status_col, "")).strip().lower()
    if status in REGRESSION_STATUSES:
        return True

    if previous_row is None:
        return False

    previous_trust = previous_row.get(trust_col)
    current_trust = row.get(trust_col)
    if previous_trust is None or current_trust is None:
        return False

    previous_value = parse_float(previous_trust, trust_col)
    current_value = parse_float(current_trust, trust_col)
    return (current_value - previous_value) <= -drop_threshold


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transitions", required=True)
    parser.add_argument("--trust-col", default="trust_score")
    parser.add_argument("--status-col", default="status")
    parser.add_argument("--drop-threshold", type=float, default=0.1)
    parser.add_argument("--max-regression-rate", type=float, default=0.0)
    args = parser.parse_args()

    if args.max_regression_rate < 0 or args.max_regression_rate > 1:
        fail(f"max-regression-rate must be between 0 and 1: {args.max_regression_rate}")

    rows = load_rows(pathlib.Path(args.transitions))
    if not rows:
        fail("transitions payload must contain rows")

    regression_flags = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        previous = rows[index - 1] if index > 0 and isinstance(rows[index - 1], dict) else None
        regression_flags.append(
            is_regression_row(row, previous, args.trust_col, args.status_col, args.drop_threshold)
        )

    if not regression_flags:
        fail("transitions payload must contain dict rows")

    regressions = sum(regression_flags)
    regression_rate = regressions / len(regression_flags)
    if regression_rate > args.max_regression_rate:
        fail(
            f"regression_rate={regression_rate:.6f} exceeds max_regression_rate={args.max_regression_rate}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
