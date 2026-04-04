#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"B99 policy coverage gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid numeric value for {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-json", required=True)
    parser.add_argument("--coverage-key", default="coverage_ratio")
    parser.add_argument("--min-coverage", type=float, default=0.0)
    parser.add_argument("--max-gaps", type=int, default=0)
    parser.add_argument("--gap-key", default="gap_events")
    args = parser.parse_args()

    try:
        payload = json.loads(pathlib.Path(args.window_json).read_text())
    except Exception as exc:
        fail(f"invalid window json: {exc}")

    if not isinstance(payload, dict):
        fail("window-json must be a JSON object")

    coverage = parse_float(payload.get(args.coverage_key), args.coverage_key)
    if coverage < args.min_coverage:
        fail(f"coverage_ratio={coverage} < min={args.min_coverage}")

    gap_value = payload.get(args.gap_key, 0)
    gaps = int(gap_value) if isinstance(gap_value, bool) or isinstance(gap_value, int) else parse_float(gap_value, args.gap_key)
    if gaps > args.max_gaps:
        fail(f"gap_events={gaps} > max={args.max_gaps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
