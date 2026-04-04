#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"F108 succession resilience gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _to_float(value: object, field: str) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {value!r}")


def _to_int(value: object, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--succession", required=True)
    parser.add_argument("--min-resilience-score", type=float, default=0.75)
    parser.add_argument("--max-open-risks", type=int, default=2)
    args = parser.parse_args()

    try:
        payload = json.loads(pathlib.Path(args.succession).read_text())
    except Exception:
        fail("invalid succession json")

    if not isinstance(payload, dict):
        fail("succession payload must be a JSON object")

    score = _to_float(payload.get("resilience_score"), "resilience_score")
    if score < args.min_resilience_score:
        fail(f"resilience_score={score}")

    risks = _to_int(payload.get("open_risk_count"), "open_risk_count")
    if risks > args.max_open_risks:
        fail(f"open_risk_count={risks}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
