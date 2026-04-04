#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"F107 recert exception age gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _to_int(value: object, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recert", required=True)
    parser.add_argument("--max-age-days", type=int, default=14)
    args = parser.parse_args()

    try:
        payload = json.loads(pathlib.Path(args.recert).read_text())
    except Exception:
        fail("invalid recert json")

    if not isinstance(payload, dict):
        fail("recert payload must be a JSON object")

    max_age = _to_int(payload.get("max_exception_age_days"), "max_exception_age_days")
    if max_age > args.max_age_days:
        fail(f"max_exception_age_days={max_age}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
