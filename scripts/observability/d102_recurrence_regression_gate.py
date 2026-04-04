#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"D102 recurrence regression gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(v, field):
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recurrence-csv", required=True)
    parser.add_argument("--value-field", default="recurrence_count")
    parser.add_argument("--max-regressions", type=int, default=0)
    parser.add_argument("--max-regression-drop", type=float, default=0.0)
    args = parser.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.recurrence_csv).read_text().splitlines()))
    values = [to_float(r.get(args.value_field), args.value_field) for r in rows]
    regressions = 0
    max_drop = 0.0
    for prev, curr in zip(values, values[1:]):
        drop = max(0.0, curr - prev)
        if drop > 0:
            regressions += 1
            max_drop = max(max_drop, drop)

    if regressions > args.max_regressions or max_drop > args.max_regression_drop:
        fail(f"regressions={regressions} max_drop={max_drop}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
