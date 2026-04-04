#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def _fail(message: str) -> None:
    print(f"F96 board review maturity gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _to_int(value: object, field: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        _fail(f"invalid integer {field}: {value!r}")


def _to_float(value: object, field: str) -> float:
    try:
        return float(str(value))
    except Exception:
        _fail(f"invalid float {field}: {value!r}")

parser = argparse.ArgumentParser()
parser.add_argument("--board", required=True)
parser.add_argument("--reviews", required=True)
parser.add_argument("--min-maturity", type=float, default=0.0)
parser.add_argument("--max-stale-reviews", type=int, default=0)
parser.add_argument("--max-untracked", type=int, default=0)
args = parser.parse_args()

board = json.loads(pathlib.Path(args.board).read_text())
if not isinstance(board, dict):
    _fail("board must be JSON object")

reviews = list(csv.DictReader(pathlib.Path(args.reviews).read_text().splitlines()))

maturity = _to_float(board.get("review_maturity", board.get("maturity_score", 0.0)), "review_maturity")
if maturity < args.min_maturity:
    _fail(f"review_maturity={maturity}")

stale = sum(1 for r in reviews if _to_int(r.get("days_since_review", 0), "days_since_review") > 30)
if stale > args.max_stale_reviews:
    _fail(f"stale_reviews={stale}")

untracked = _to_int(board.get("untracked_items", board.get("untracked", 0)), "untracked_items")
if untracked > args.max_untracked:
    _fail(f"untracked_items={untracked}")
