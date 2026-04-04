#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def parse_float(value: object, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"non-numeric {label}: {value!r}")


def parse_stats(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"failed to parse JSON stats from {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"stats payload must be a JSON object: {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats", required=True)
    parser.add_argument("--current-latency-key", default="scheduler_latency_ms")
    parser.add_argument("--baseline-latency-key", default="scheduler_latency_baseline_ms")
    parser.add_argument("--max-regression-ratio", type=float, default=1.0)
    args = parser.parse_args()

    try:
        stats = parse_stats(pathlib.Path(args.stats))
        current = parse_float(
            stats.get(args.current_latency_key),
            f"missing/invalid value for {args.current_latency_key}",
        )
        baseline = parse_float(
            stats.get(args.baseline_latency_key),
            f"missing/invalid value for {args.baseline_latency_key}",
        )
    except (OSError, ValueError) as exc:
        print(f"B89 scheduler latency regression gate failed: {exc}", file=sys.stderr)
        return 2

    if baseline <= 0:
        print(
            "B89 scheduler latency regression gate failed: baseline latency must be greater than 0",
            file=sys.stderr,
        )
        return 2

    regression_ratio = current / baseline
    if regression_ratio > args.max_regression_ratio:
        print(
            "B89 scheduler latency regression gate failed: "
            f"regression_ratio={regression_ratio:.6f} > max={args.max_regression_ratio}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
