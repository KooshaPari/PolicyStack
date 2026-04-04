#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E102 custody signature count gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _parse_json_rows(path: pathlib.Path) -> list[dict]:
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        for key in ("custody", "items", "records", "entries"):
            rows = data.get(key)
            if isinstance(rows, list):
                return rows
        fail("custody payload must include custody/items/records/entries")
    if not isinstance(data, list):
        fail("custody payload must be list or object with custody/items/records/entries")
    return data


def to_int(v, field: str) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--custody", required=True)
    parser.add_argument("--sig-col", default="signatures")
    parser.add_argument("--min-signatures", type=int, default=1)
    parser.add_argument("--max-under-signed", type=int, default=0)
    args = parser.parse_args()

    rows = _parse_json_rows(pathlib.Path(args.custody))
    under_signed = 0

    for row in rows:
        value = row.get(args.sig_col, 0)
        if isinstance(value, list):
            sig_count = len(value)
        else:
            sig_count = to_int(value, args.sig_col)
        if sig_count < args.min_signatures:
            under_signed += 1

    if under_signed > args.max_under_signed:
        fail(f"under_signed_count={under_signed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
