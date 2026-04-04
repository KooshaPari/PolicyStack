#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"F115 recert exception threshold gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_int(value: object, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recert", required=True)
    parser.add_argument("--exception-count-field", default="exception_count")
    parser.add_argument("--max-exceptions", type=int, default=25)
    parser.add_argument("--open-exception-field", default="open_exception_count")
    parser.add_argument("--max-open-exceptions", type=int, default=10)
    args = parser.parse_args()

    try:
        payload = json.loads(pathlib.Path(args.recert).read_text())
    except Exception:
        fail("invalid recert json")

    if not isinstance(payload, dict):
        fail("recert payload must be a JSON object")

    total = to_int(payload.get(args.exception_count_field), args.exception_count_field)
    if total > args.max_exceptions:
        fail(f"{args.exception_count_field}={total} > {args.max_exceptions}")

    open_exceptions = to_int(payload.get(args.open_exception_field), args.open_exception_field)
    if open_exceptions > args.max_open_exceptions:
        fail(f"{args.open_exception_field}={open_exceptions} > {args.max_open_exceptions}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
