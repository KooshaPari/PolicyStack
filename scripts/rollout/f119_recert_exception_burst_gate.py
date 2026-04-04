#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E119 recert exception burst gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


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
            fail("invalid recert csv")
        if not rows:
            fail("recert csv must contain at least one row")
        return [dict(row) for row in rows]

    try:
        payload = json.loads(path.read_text())
    except Exception:
        fail("invalid recert json")

    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and payload and all(isinstance(item, dict) for item in payload):
        return list(payload)
    fail("recert payload must be a JSON object or non-empty list of objects")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recert", required=True)
    parser.add_argument("--burst-count-field", default="exception_burst_count")
    parser.add_argument("--max-burst-count", type=int, default=5)
    parser.add_argument("--open-exception-field", default="open_exception_count")
    parser.add_argument("--max-open-exceptions", type=int, default=10)
    args = parser.parse_args()

    records = load_records(pathlib.Path(args.recert))
    for index, record in enumerate(records):
        burst_count = to_int(record.get(args.burst_count_field), args.burst_count_field, index)
        if burst_count > args.max_burst_count:
            fail(f"{args.burst_count_field}={burst_count} > {args.max_burst_count} at index {index}")

        open_exceptions = to_int(record.get(args.open_exception_field), args.open_exception_field, index)
        if open_exceptions > args.max_open_exceptions:
            fail(
                f"{args.open_exception_field}={open_exceptions} > "
                f"{args.max_open_exceptions} at index {index}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
