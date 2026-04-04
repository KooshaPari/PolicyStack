#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"F102 board review staleness gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", required=True)
    parser.add_argument("--max-days", type=float, default=30.0)
    args = parser.parse_args()

    data = json.loads(pathlib.Path(args.board).read_text())
    if not isinstance(data, dict) or not data.get("board_review_staleness_monitoring", True):
        fail("board_review_staleness_monitoring is disabled")

    max_stale = float(data.get("max_stale_days", 0.0))
    if max_stale > args.max_days:
        fail(f"max_stale_days={max_stale}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
