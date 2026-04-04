#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E97 trust failover watchdog gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_int(v, field):
    try:
        return int(v)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--watchdog", required=True)
    parser.add_argument("--status-col", default="status")
    parser.add_argument("--time-col", default="duration_ms")
    parser.add_argument("--max-unsupervised", type=int, default=0)
    parser.add_argument("--max-avg-time", type=int, default=0)
    args = parser.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.watchdog).read_text().splitlines()))
    active = [r for r in rows if str(r.get(args.status_col, "")).strip().lower() not in {"ok", "nominal", "idle"}]
    unsupervised = len(active)
    total_time = sum(parse_int(r.get(args.time_col, 0), args.time_col) for r in active)
    avg_time = (total_time / unsupervised) if unsupervised else 0
    if unsupervised > args.max_unsupervised:
        fail(f"unsupervised_failover_count={unsupervised}")
    if avg_time > args.max_avg_time:
        fail(f"avg_unsupervised_time={avg_time}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
