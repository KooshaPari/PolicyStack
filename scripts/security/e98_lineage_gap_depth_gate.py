#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E98 lineage gap depth gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_int(v, field):
    try:
        return int(v)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lineage", required=True)
    parser.add_argument("--max-gap-depth", type=int, default=0)
    args = parser.parse_args()

    data = json.loads(pathlib.Path(args.lineage).read_text())
    if not isinstance(data, dict):
        fail("lineage must be object")

    gaps = data.get("gaps", [])
    if not isinstance(gaps, list):
        fail("lineage.gaps must be list")

    max_depth = 0
    for g in gaps:
        if isinstance(g, dict):
            max_depth = max(max_depth, to_int(g.get("depth", 0), "depth"))

    if max_depth > args.max_gap_depth:
        fail(f"max_gap_depth={max_depth}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
