#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


REGRESSION_STATUSES = {"regression", "degradation", "drop", "error", "fail"}


def fail(message: str) -> None:
    print(f"E114 trust regression window gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(value: object, field: str) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {value!r}")


def load_rows(path: pathlib.Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        return list(csv.DictReader(path.read_text().splitlines()))
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("transitions", "records", "items", "entries"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
    fail("transitions payload must be list or object with transitions/records/items/entries")


def is_regression_row(
    row: dict,
    previous_row: dict | None,
    trust_col: str,
    status_col: str,
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
    return current_value - previous_value <= -0.1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transitions", required=True)
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--max-window-regressions", type=int, default=0)
    parser.add_argument("--trust-col", default="trust_score")
    parser.add_argument("--status-col", default="status")
    args = parser.parse_args()

    if args.window_size <= 0:
        fail(f"window-size must be positive: {args.window_size}")

    rows = load_rows(pathlib.Path(args.transitions))
    if not rows:
        fail("transitions payload must contain rows")

    regression_flags = [
        is_regression_row(
            row,
            rows[index - 1] if index > 0 and isinstance(rows[index - 1], dict) else None,
            args.trust_col,
            args.status_col,
        )
        for index, row in enumerate(rows)
        if isinstance(row, dict)
    ]

    window_regression_count = 0
    for start in range(0, len(regression_flags) - args.window_size + 1):
        window = regression_flags[start : start + args.window_size]
        if (sum(window) / args.window_size) > 0.5:
            window_regression_count += 1

    if window_regression_count > args.max_window_regressions:
        fail(f"window_regressions={window_regression_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
