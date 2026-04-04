#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"C111 replay density gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_int(v, field):
    try:
        return int(v)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replays", required=True)
    parser.add_argument("--max-failed-replays", type=int, default=0)
    parser.add_argument("--max-empty-replays", type=int, default=0)
    parser.add_argument("--max-burst-count", type=int, default=0)
    args = parser.parse_args()

    payload = json.loads(pathlib.Path(args.replays).read_text())
    rows = payload.get("replays", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        fail("replays JSON must be a list or contain replays")

    failed = 0
    empty = 0
    burst_count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if int(row.get("event_count", 1)) <= 0:
            empty += 1

        status = str(row.get("status", "")).strip().lower()
        if status in {"fail", "failed", "error"}:
            failed += 1

        if int(row.get("burst_events", 0)) > 0:
            burst_count += 1

    if failed > args.max_failed_replays:
        fail(f"failed_replays={failed}")

    if empty > args.max_empty_replays:
        fail(f"empty_replays={empty}")

    if burst_count > args.max_burst_count:
        fail(f"burst_replays={burst_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
