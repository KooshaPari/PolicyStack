#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"A103 revocation latency regression gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(value: str, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError:
        fail(f"invalid float in {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revocations", required=True)
    parser.add_argument("--time-field", default="window")
    parser.add_argument("--latency-field", default="p95_latency_ms")
    parser.add_argument("--max-regressions", type=int, default=0)
    parser.add_argument("--max-regression-drop", type=float, default=0.0)
    args = parser.parse_args()

    rows = sorted(
        csv.DictReader(pathlib.Path(args.revocations).read_text().splitlines()),
        key=lambda r: str(r.get(args.time_field, "")),
    )
    if len(rows) < 2:
        fail("not enough revocation windows")

    latencies = [to_float(r.get(args.latency_field, "0"), args.latency_field) for r in rows]
    regressions = 0
    max_drop = 0.0
    for prev, curr in zip(latencies, latencies[1:]):
        drop = curr - prev
        if drop > 0:
            max_drop = max(max_drop, drop)
            regressions += 1

    if regressions > args.max_regressions:
        fail(f"regressions={regressions}")
    if max_drop > args.max_regression_drop:
        fail(f"max_regression_drop={max_drop}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
