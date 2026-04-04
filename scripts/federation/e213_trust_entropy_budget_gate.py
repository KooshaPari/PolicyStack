#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


UNSTABLE_STATUSES = {
    "regression",
    "degradation",
    "drop",
    "error",
    "fail",
    "rollback",
}


def fail(message: str) -> None:
    print(f"E213 trust stability budget gate failed: {message}", file=sys.stderr)
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
    fail(
        "transitions payload must be list or object with "
        "transitions/records/items/entries/attestations"
    )


def is_unstable_transition(
    row: dict,
    previous_row: dict | None,
    trust_col: str,
    status_col: str,
    instability_threshold: float,
) -> bool:
    status = str(row.get(status_col, "")).strip().lower()
    if status in UNSTABLE_STATUSES:
        return True

    if previous_row is None:
        return False

    previous_value = previous_row.get(trust_col)
    current_value = row.get(trust_col)
    if previous_value is None or current_value is None:
        return False

    return abs(parse_float(current_value, trust_col) - parse_float(previous_value, trust_col)) > (
        instability_threshold
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transitions", required=True)
    parser.add_argument("--trust-col", default="trust_score")
    parser.add_argument("--status-col", default="status")
    parser.add_argument("--instability-threshold", type=float, default=0.2)
    parser.add_argument("--max-unstable", type=int, default=0)
    parser.add_argument("--max-unstable-rate", type=float, default=0.0)
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--max-unstable-per-window", type=int, default=1)
    parser.add_argument("--max-window-violations", type=int, default=0)
    parser.add_argument("--min-stable-window-ratio", type=float, default=1.0)
    args = parser.parse_args()

    if args.instability_threshold < 0:
        fail(
            "instability-threshold must be non-negative: "
            f"{args.instability_threshold}"
        )
    if args.max_unstable < 0:
        fail(f"max-unstable must be non-negative: {args.max_unstable}")
    if args.max_unstable_rate < 0 or args.max_unstable_rate > 1:
        fail(f"max-unstable-rate must be between 0 and 1: {args.max_unstable_rate}")
    if args.window_size <= 0:
        fail(f"window-size must be positive: {args.window_size}")
    if args.max_unstable_per_window < 0:
        fail(
            "max-unstable-per-window must be non-negative: "
            f"{args.max_unstable_per_window}"
        )
    if args.max_window_violations < 0:
        fail(f"max-window-violations must be non-negative: {args.max_window_violations}")
    if args.min_stable_window_ratio < 0 or args.min_stable_window_ratio > 1:
        fail(
            "min-stable-window-ratio must be between 0 and 1: "
            f"{args.min_stable_window_ratio}"
        )

    rows = load_rows(pathlib.Path(args.transitions))
    if not rows:
        fail("transitions payload must contain rows")

    unstable_flags = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        previous = rows[index - 1] if index > 0 and isinstance(rows[index - 1], dict) else None
        unstable_flags.append(
            is_unstable_transition(
                row,
                previous,
                args.trust_col,
                args.status_col,
                args.instability_threshold,
            )
        )

    if not unstable_flags:
        fail("transitions payload must contain dict rows")

    unstable = sum(unstable_flags)
    unstable_rate = unstable / len(unstable_flags)
    if unstable > args.max_unstable:
        fail(f"unstable={unstable} exceeds max_unstable={args.max_unstable}")
    if unstable_rate > args.max_unstable_rate:
        fail(
            f"unstable_rate={unstable_rate:.6f} exceeds max_unstable_rate="
            f"{args.max_unstable_rate}"
        )

    window_count = len(unstable_flags) - args.window_size + 1
    if window_count <= 0:
        fail(
            f"window-size={args.window_size} exceeds available rows={len(unstable_flags)}"
        )

    violations = 0
    for start in range(window_count):
        window = unstable_flags[start : start + args.window_size]
        if sum(window) > args.max_unstable_per_window:
            violations += 1

    stable_ratio = (window_count - violations) / window_count
    if violations > args.max_window_violations:
        fail(
            f"window_violations={violations} exceeds max_window_violations="
            f"{args.max_window_violations}"
        )
    if stable_ratio < args.min_stable_window_ratio:
        fail(
            f"stable_window_ratio={stable_ratio:.6f} below min_stable_window_ratio="
            f"{args.min_stable_window_ratio}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
