#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"F111 recert exception load gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _to_int(value: object, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recert", required=True)
    parser.add_argument("--max-total-exceptions", type=int, default=25)
    args = parser.parse_args()

    try:
        payload = json.loads(pathlib.Path(args.recert).read_text())
    except Exception:
        fail("invalid recert json")

    if not isinstance(payload, dict):
        fail("recert payload must be a JSON object")

    total_exceptions = _to_int(payload.get("exception_count"), "exception_count")
    if total_exceptions > args.max_total_exceptions:
        fail(f"exception_count={total_exceptions}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
