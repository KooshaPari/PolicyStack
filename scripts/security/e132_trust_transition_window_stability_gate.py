#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


UNSTABLE_STATUSES = {"unstable", "regression", "degradation", "drop", "error", "fail", "rollback"}


def fail(message: str) -> None:
    print(f"E132 trust transition window stability gate failed: {message}", file=sys.stderr)
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


def is_unstable_transition(
    row: dict,
    status_col: str,
    trust_delta_col: str,
    instability_threshold: float,
) -> bool:
    status = str(row.get(status_col, "")).strip().lower()
    if status in UNSTABLE_STATUSES:
        return True

    trust_delta = row.get(trust_delta_col)
    if trust_delta is None or str(trust_delta).strip() == "":
        return False

    return abs(parse_float(trust_delta, trust_delta_col)) > instability_threshold


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transitions", required=True)
    parser.add_argument("--status-col", default="status")
    parser.add_argument("--trust-delta-col", default="trust_delta")
    parser.add_argument("--instability-threshold", type=float, default=0.2)
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--max-unstable-per-window", type=int, default=0)
    parser.add_argument("--max-window-violations", type=int, default=0)
    args = parser.parse_args()

    if args.window_size <= 0:
        fail(f"window-size must be positive: {args.window_size}")
    if args.max_unstable_per_window < 0:
        fail(f"max-unstable-per-window must be non-negative: {args.max_unstable_per_window}")
    if args.max_window_violations < 0:
        fail(f"max-window-violations must be non-negative: {args.max_window_violations}")

    rows = load_rows(pathlib.Path(args.transitions))
    if not rows:
        fail("transitions payload must contain rows")

    unstable_flags = []
    for row in rows:
        if isinstance(row, dict):
            unstable_flags.append(
                is_unstable_transition(
                    row,
                    args.status_col,
                    args.trust_delta_col,
                    args.instability_threshold,
                )
            )

    if not unstable_flags:
        fail("transitions payload must contain dict rows")

    violations = 0
    for start in range(0, len(unstable_flags) - args.window_size + 1):
        window = unstable_flags[start : start + args.window_size]
        if sum(window) > args.max_unstable_per_window:
            violations += 1

    if violations > args.max_window_violations:
        fail(f"window_violations={violations} exceeds max_window_violations={args.max_window_violations}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
