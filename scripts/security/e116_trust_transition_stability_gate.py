#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E116 trust transition stability gate failed: {message}", file=sys.stderr)
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transitions", required=True)
    parser.add_argument("--score-col", default="trust_score")
    parser.add_argument("--max-oscillations", type=int, default=0)
    parser.add_argument("--oscillation-threshold", type=float, default=0.2)
    args = parser.parse_args()

    rows = load_rows(pathlib.Path(args.transitions))
    if len(rows) < 2:
        fail("transitions payload must contain at least 2 rows")

    oscillations = 0
    prev_score = parse_float(rows[0].get(args.score_col), args.score_col)
    prev_direction = None
    for row in rows[1:]:
        score = parse_float(row.get(args.score_col), args.score_col)
        delta = score - prev_score

        if abs(delta) >= args.oscillation_threshold:
            direction = 1 if delta > 0 else -1
            if prev_direction is not None and direction == -prev_direction:
                oscillations += 1
            prev_direction = direction

        prev_score = score

    if oscillations > args.max_oscillations:
        fail(f"oscillation_count={oscillations}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
