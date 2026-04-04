#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"F113 board threshold gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(value: object, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {value!r}")


def to_int(value: object, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", required=True)
    parser.add_argument("--fatigue-score-field", default="review_fatigue_score")
    parser.add_argument("--max-fatigue-score", type=float, default=0.45)
    parser.add_argument("--actions-field", default="open_review_actions")
    parser.add_argument("--max-open-actions", type=int, default=5)
    args = parser.parse_args()

    try:
        payload = json.loads(pathlib.Path(args.board).read_text())
    except Exception:
        fail("invalid board json")

    if not isinstance(payload, dict):
        fail("board payload must be a JSON object")

    fatigue = to_float(payload.get(args.fatigue_score_field), args.fatigue_score_field)
    if fatigue > args.max_fatigue_score:
        fail(f"{args.fatigue_score_field}={fatigue} > {args.max_fatigue_score}")

    actions = to_int(payload.get(args.actions_field), args.actions_field)
    if actions > args.max_open_actions:
        fail(f"{args.actions_field}={actions} > {args.max_open_actions}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
