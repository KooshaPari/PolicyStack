#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E113 trust regression tally gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_rows(path: pathlib.Path) -> list[dict]:
    try:
        if path.suffix.lower() == ".csv":
            return list(csv.DictReader(path.open()))
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid transitions input: {exc}")

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("transitions", "records", "items", "entries"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
    fail("transitions payload must be list or dict with transitions|records|items|entries")


def parse_float(value: object, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transitions", required=True)
    parser.add_argument("--trust-col", default="trust_score")
    parser.add_argument("--max-regressions", type=int, default=0)
    parser.add_argument("--max-step-delta", type=float, default=0.0)
    parser.add_argument("--status-col", default="status")
    args = parser.parse_args()

    rows = load_rows(pathlib.Path(args.transitions))
    if not rows:
        fail("transitions payload must contain rows")

    regression_statuses = {"regression", "degradation", "drop", "fail", "error", "rollback"}

    regressions = 0
    previous_score: float | None = None

    for row in rows:
        status = str(row.get(args.status_col, "")).strip().lower()
        score = parse_float(row.get(args.trust_col), args.trust_col)

        is_regression = status in regression_statuses
        is_step_drop = False
        if previous_score is not None and score - previous_score < -args.max_step_delta:
            is_step_drop = True

        if is_regression or is_step_drop:
            regressions += 1

        previous_score = score

    if regressions > args.max_regressions:
        fail(f"regressions={regressions} exceeds max_regressions={args.max_regressions}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
