#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def parse_float(value: object, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"non-numeric {label}: {value!r}") from exc


def parse_csv(path: pathlib.Path) -> list[dict[str, str]]:
    try:
        rows = list(csv.DictReader(path.read_text().splitlines()))
    except OSError as exc:
        raise ValueError(f"failed to read CSV from {path}: {exc}") from exc
    return rows


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--recovered-col", default="capa_recovered_count")
    p.add_argument("--expected-col", default="capa_expected_recoveries")
    p.add_argument("--target-recovery-rate", type=float, default=1.0)
    p.add_argument("--max-variance", type=float, default=0.0)
    p.add_argument("--max-breaches", type=int, default=0)
    p.add_argument("--require-data", action="store_true")
    args = p.parse_args()

    try:
        rows = parse_csv(pathlib.Path(args.csv))
    except ValueError as exc:
        print(f"B92 capa recovery stability gate failed: {exc}", file=sys.stderr)
        return 2

    breaches = 0
    for row in rows:
        try:
            recovered = parse_float(
                row.get(args.recovered_col, 0.0),
                f"missing/invalid value for {args.recovered_col}",
            )
            expected = parse_float(
                row.get(args.expected_col, 0.0),
                f"missing/invalid value for {args.expected_col}",
            )
        except ValueError as exc:
            print(f"B92 capa recovery stability gate failed: {exc}", file=sys.stderr)
            return 2

        if expected <= 0:
            continue
        if abs((recovered / expected) - args.target_recovery_rate) > args.max_variance:
            breaches += 1

    if args.require_data and not rows:
        print("B92 capa recovery stability gate failed: no recovery rows to evaluate", file=sys.stderr)
        return 2

    if breaches > args.max_breaches:
        print(
            "B92 CAPA recovery stability gate failed: "
            f"breaches={breaches} > max_breaches={args.max_breaches}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
