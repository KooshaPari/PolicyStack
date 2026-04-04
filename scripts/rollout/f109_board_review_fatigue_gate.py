#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"F109 board review fatigue gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _to_float(value: object, field: str) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {value!r}")


def _to_int(value: object, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", required=True)
    parser.add_argument("--max-fatigue-score", type=float, default=0.45)
    parser.add_argument("--max-open-actions", type=int, default=5)
    args = parser.parse_args()

    try:
        payload = json.loads(pathlib.Path(args.board).read_text())
    except Exception:
        fail("invalid board json")

    if not isinstance(payload, dict):
        fail("board payload must be a JSON object")

    fatigue_score = _to_float(payload.get("review_fatigue_score"), "review_fatigue_score")
    if fatigue_score > args.max_fatigue_score:
        fail(f"review_fatigue_score={fatigue_score}")

    open_actions = _to_int(payload.get("open_review_actions"), "open_review_actions")
    if open_actions > args.max_open_actions:
        fail(f"open_review_actions={open_actions}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
