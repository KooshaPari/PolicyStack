#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"C114 replay stability gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(v, field):
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replays", required=True)
    parser.add_argument("--min-success-rate", type=float, default=0.95)
    parser.add_argument("--max-error-rate", type=float, default=0.05)
    args = parser.parse_args()

    payload = json.loads(pathlib.Path(args.replays).read_text())
    rows = payload.get("replays", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        fail("replays JSON must be a list or contain replays")

    total = 0
    ok = 0
    errors = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        total += 1
        status = str(row.get("status", "")).strip().lower()
        if status in {"failed", "error", "fatal"}:
            errors += 1
        else:
            ok += 1

    if total == 0:
        fail("replays JSON contains no entries")

    success_rate = ok / total
    error_rate = errors / total
    if success_rate < args.min_success_rate:
        fail(f"success_rate={success_rate:.6f}")
    if error_rate > args.max_error_rate:
        fail(f"error_rate={error_rate:.6f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
