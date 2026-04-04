#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"F114 KPI threshold gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(value: object, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {value!r}")


def to_int(value: object, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kpi", required=True)
    parser.add_argument("--window-open-field", default="open_windows")
    parser.add_argument("--max-open-windows", type=int, default=0)
    parser.add_argument("--quality-score-field", default="quality_score")
    parser.add_argument("--min-quality-score", type=float, default=0.95)
    args = parser.parse_args()

    try:
        payload = json.loads(pathlib.Path(args.kpi).read_text())
    except Exception:
        fail("invalid kpi json")

    if not isinstance(payload, dict):
        fail("kpi payload must be a JSON object")

    windows = to_int(payload.get(args.window_open_field), args.window_open_field)
    if windows > args.max_open_windows:
        fail(f"{args.window_open_field}={windows} > {args.max_open_windows}")

    quality = to_float(payload.get(args.quality_score_field), args.quality_score_field)
    if quality < args.min_quality_score:
        fail(f"{args.quality_score_field}={quality} < {args.min_quality_score}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
