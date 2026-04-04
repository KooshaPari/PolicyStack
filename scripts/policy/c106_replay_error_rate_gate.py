#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"C106 replay error rate gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(v, field):
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def to_int(v, field):
    try:
        return int(v)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-csv", required=True)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument("--max-error-count", type=int, default=0)
    args = parser.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.replay_csv).read_text().splitlines()))
    if not rows:
        fail("replay CSV is empty")

    total = 0
    errors = 0
    for row in rows:
        total += 1
        if str(row.get("status", "")).lower() in {"error", "failed", "timeout"}:
            errors += 1
        elif to_int(row.get("error_count", 0), "error_count") > 0:
            errors += 1

    error_rate = to_float(errors, "errors") / float(total)
    if error_rate > args.max_error_rate:
        fail(f"error_rate={error_rate:.4f}")

    if errors > args.max_error_count:
        fail(f"error_count={errors}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
