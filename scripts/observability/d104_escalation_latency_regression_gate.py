#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"D104 escalation latency regression gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(v, field):
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--escalations-csv", required=True)
    parser.add_argument("--latency-field", default="latency_ms")
    parser.add_argument("--time-field", default="window")
    parser.add_argument("--max-regressions", type=int, default=0)
    parser.add_argument("--max-drop", type=float, default=0.0)
    args = parser.parse_args()

    rows = sorted(
        csv.DictReader(pathlib.Path(args.escalations_csv).read_text().splitlines()),
        key=lambda r: str(r.get(args.time_field, "")),
    )
    lat = [to_float(r.get(args.latency_field), args.latency_field) for r in rows]
    regressions = 0
    max_drop = 0.0
    for prev, curr in zip(lat, lat[1:]):
        d = curr - prev
        if d > 0:
            regressions += 1
            max_drop = max(max_drop, d)

    if regressions > args.max_regressions or max_drop > args.max_drop:
        fail(f"regressions={regressions} max_drop={max_drop}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
