#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(
        f"E150 attestation entropy window budget gate failed: {message}",
        file=sys.stderr,
    )
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
        fail(f"invalid attestations input: {exc}")

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("attestations", "records", "items", "entries", "transitions"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
    fail("attestations payload must be list or object with attestations/records/items/entries/transitions")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attestations", required=True)
    parser.add_argument("--entropy-col", default="entropy")
    parser.add_argument("--entropy-delta-col", default="entropy_delta")
    parser.add_argument("--drop-threshold", type=float, default=0.0)
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--max-regressions-per-window", type=int, default=0)
    parser.add_argument("--max-window-violations", type=int, default=0)
    args = parser.parse_args()

    if args.window_size <= 0:
        fail(f"window-size must be positive: {args.window_size}")
    if args.max_regressions_per_window < 0:
        fail(
            "max-regressions-per-window must be non-negative: "
            f"{args.max_regressions_per_window}"
        )
    if args.max_window_violations < 0:
        fail(f"max-window-violations must be non-negative: {args.max_window_violations}")

    rows = load_rows(pathlib.Path(args.attestations))
    if not rows:
        fail("attestations payload must contain rows")

    regression_flags = []
    previous_entropy = None
    for row in rows:
        if not isinstance(row, dict):
            continue

        delta_value = row.get(args.entropy_delta_col)
        if delta_value is not None and str(delta_value).strip() != "":
            entropy_delta = parse_float(delta_value, args.entropy_delta_col)
        else:
            entropy_value = parse_float(row.get(args.entropy_col), args.entropy_col)
            if previous_entropy is None:
                previous_entropy = entropy_value
                regression_flags.append(False)
                continue
            entropy_delta = entropy_value - previous_entropy
            previous_entropy = entropy_value

        regression_flags.append(entropy_delta <= -args.drop_threshold)

    if not regression_flags:
        fail("attestations payload must contain dict rows")

    if args.window_size > len(regression_flags):
        fail(
            f"window-size={args.window_size} exceeds available rows={len(regression_flags)}"
        )

    violations = 0
    for start in range(0, len(regression_flags) - args.window_size + 1):
        window = regression_flags[start : start + args.window_size]
        if sum(window) > args.max_regressions_per_window:
            violations += 1

    if violations > args.max_window_violations:
        fail(
            f"window_violations={violations} exceeds max_window_violations={args.max_window_violations}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
