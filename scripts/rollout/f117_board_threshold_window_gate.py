#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E117 board threshold window gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(value: object, field: str, index: int) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid float in {field} at index {index}: {value!r}")


def to_int(value: object, field: str, index: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"invalid int in {field} at index {index}: {value!r}")


def load_records(path: pathlib.Path) -> list[dict[str, object]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        except Exception:
            fail("invalid board csv")
        if not rows:
            fail("board csv must contain at least one row")
        return [dict(row) for row in rows]

    try:
        payload = json.loads(path.read_text())
    except Exception:
        fail("invalid board json")

    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and payload and all(isinstance(item, dict) for item in payload):
        return list(payload)
    fail("board payload must be a JSON object or non-empty list of objects")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", required=True)
    parser.add_argument("--fatigue-score-field", default="review_fatigue_score")
    parser.add_argument("--max-fatigue-score", type=float, default=0.45)
    parser.add_argument("--actions-field", default="open_review_actions")
    parser.add_argument("--max-open-actions", type=int, default=5)
    args = parser.parse_args()

    records = load_records(pathlib.Path(args.board))
    for index, record in enumerate(records):
        fatigue = to_float(record.get(args.fatigue_score_field), args.fatigue_score_field, index)
        if fatigue > args.max_fatigue_score:
            fail(
                f"{args.fatigue_score_field}={fatigue} > {args.max_fatigue_score} at index {index}"
            )

        actions = to_int(record.get(args.actions_field), args.actions_field, index)
        if actions > args.max_open_actions:
            fail(f"{args.actions_field}={actions} > {args.max_open_actions} at index {index}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
