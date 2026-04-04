#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E127 recert exception window gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--exception-window-days-field", default="exception_window_days")
    parser.add_argument("--max-exception-window-days", type=int, default=30)
    parser.add_argument("--window-breach-count-field", default="exception_window_breach_count")
    parser.add_argument("--max-window-breach-count", type=int, default=0)
    args = parser.parse_args()

    records = load_records(pathlib.Path(args.recert))
    for index, record in enumerate(records):
        exception_window_days = to_int(
            record.get(args.exception_window_days_field), args.exception_window_days_field, index
        )
        if exception_window_days > args.max_exception_window_days:
            fail(
                f"{args.exception_window_days_field}={exception_window_days} > "
                f"{args.max_exception_window_days} at index {index}"
            )

        window_breach_count = to_int(
            record.get(args.window_breach_count_field), args.window_breach_count_field, index
        )
        if window_breach_count > args.max_window_breach_count:
            fail(
                f"{args.window_breach_count_field}={window_breach_count} > "
                f"{args.max_window_breach_count} at index {index}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
