#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E144 trust transition window budget gate failed: {message}", file=sys.stderr)
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transitions", required=True)
    parser.add_argument("--trust-delta-col", default="trust_delta")
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--max-total-transition-per-window", type=float, default=0.0)
    parser.add_argument("--max-average-transition-per-window", type=float, default=0.0)
    parser.add_argument("--max-transition-per-window", type=float, default=0.0)
    parser.add_argument("--max-window-violations", type=int, default=0)
    args = parser.parse_args()

    if args.window_size <= 0:
        fail(f"window-size must be positive: {args.window_size}")
    if args.max_total_transition_per_window < 0:
        fail(
            "max-total-transition-per-window must be non-negative: "
            f"{args.max_total_transition_per_window}"
        )
    if args.max_average_transition_per_window < 0:
        fail(
            "max-average-transition-per-window must be non-negative: "
            f"{args.max_average_transition_per_window}"
        )
    if args.max_transition_per_window < 0:
        fail(
            "max-transition-per-window must be non-negative: "
            f"{args.max_transition_per_window}"
        )
    if args.max_window_violations < 0:
        fail(f"max-window-violations must be non-negative: {args.max_window_violations}")

    rows = load_rows(pathlib.Path(args.transitions))
    if not rows:
        fail("transitions payload must contain rows")

    transition_values = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        delta_value = row.get(args.trust_delta_col)
        if delta_value is None or str(delta_value).strip() == "":
            fail(f"missing trust delta in {args.trust_delta_col}")
        transition_values.append(abs(parse_float(delta_value, args.trust_delta_col)))

    if not transition_values:
        fail("transitions payload must contain dict rows with trust delta values")

    if args.window_size > len(transition_values):
        fail(
            f"window-size={args.window_size} exceeds available rows={len(transition_values)}"
        )

    violations = 0
    for start in range(0, len(transition_values) - args.window_size + 1):
        window = transition_values[start : start + args.window_size]
        total_transition = sum(window)
        average_transition = total_transition / len(window)
        peak_transition = max(window)
        if (
            total_transition > args.max_total_transition_per_window
            or average_transition > args.max_average_transition_per_window
            or peak_transition > args.max_transition_per_window
        ):
            violations += 1

    if violations > args.max_window_violations:
        fail(f"window_violations={violations} exceeds max_window_violations={args.max_window_violations}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
