#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"B109 capa stability gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def parse_float(value, field):
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"invalid numeric value for {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics-json", required=True)
    parser.add_argument("--stability-key", default="stability_ratio")
    parser.add_argument("--min-stability", type=float, default=0.0)
    parser.add_argument("--max-drop", type=float, default=0.0)
    parser.add_argument("--previous-stability-key", default="previous_stability_ratio")
    args = parser.parse_args()

    try:
        payload = json.loads(pathlib.Path(args.metrics_json).read_text())
    except Exception as exc:
        fail(f"invalid metrics json: {exc}")

    if not isinstance(payload, dict):
        fail("metrics-json must be a JSON object")

    current = parse_float(payload.get(args.stability_key), args.stability_key)
    if current < args.min_stability:
        fail(f"stability_ratio={current} < min={args.min_stability}")

    previous = parse_float(
        payload.get(args.previous_stability_key), args.previous_stability_key
    )
    drop = previous - current
    if drop > args.max_drop:
        fail(
            f"stability_drop={drop} > max_allowed={args.max_drop}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
