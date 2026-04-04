#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def parse_float(value: object, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"non-numeric {label}: {value!r}") from exc


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
    parser.add_argument("--downgrade-key", default="preflight_downgrade_count")
    parser.add_argument("--total-key", default="preflight_total")
    parser.add_argument("--max-downgrade-rate", type=float, default=0.0)
    args = parser.parse_args()

    try:
        stats = parse_stats(pathlib.Path(args.stats))
        downgrades = parse_float(
            stats.get(args.downgrade_key),
            f"missing/invalid value for {args.downgrade_key}",
        )
        total = parse_float(
            stats.get(args.total_key),
            f"missing/invalid value for {args.total_key}",
        )
    except (OSError, ValueError) as exc:
        print(f"B90 signature preflight downgrade gate failed: {exc}", file=sys.stderr)
        return 2

    downgrade_rate = (downgrades / total) if total > 0 else 0.0
    if downgrade_rate > args.max_downgrade_rate:
        print(
            "B90 signature preflight downgrade gate failed: "
            f"downgrade_rate={downgrade_rate:.6f} > max={args.max_downgrade_rate}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
