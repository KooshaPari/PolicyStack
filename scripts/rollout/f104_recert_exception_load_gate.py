#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"F104 recert exception load gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_int(v, field):
    try:
        return int(v)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recert", required=True)
    parser.add_argument("--max-load", type=int, default=0)
    args = parser.parse_args()

    data = json.loads(pathlib.Path(args.recert).read_text())
    load = to_int(data.get("exception_queue_load"), "exception_queue_load")
    if load > args.max_load:
        fail(f"exception_queue_load={load}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
