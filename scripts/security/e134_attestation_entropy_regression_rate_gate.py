#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E134 attestation entropy regression rate gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--max-regression-rate", type=float, default=0.0)
    args = parser.parse_args()

    if args.max_regression_rate < 0 or args.max_regression_rate > 1:
        fail(f"max-regression-rate must be between 0 and 1: {args.max_regression_rate}")

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
            regression_flags.append(
                parse_float(delta_value, args.entropy_delta_col) <= -args.drop_threshold
            )
            continue

        entropy_value = parse_float(row.get(args.entropy_col), args.entropy_col)
        if previous_entropy is None:
            regression_flags.append(False)
        else:
            regression_flags.append((entropy_value - previous_entropy) <= -args.drop_threshold)
        previous_entropy = entropy_value

    if not regression_flags:
        fail("attestations payload must contain dict rows")

    regressions = sum(regression_flags)
    regression_rate = regressions / len(regression_flags)
    if regression_rate > args.max_regression_rate:
        fail(
            f"regression_rate={regression_rate:.6f} exceeds max_regression_rate={args.max_regression_rate}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
