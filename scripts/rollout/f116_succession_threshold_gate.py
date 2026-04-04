#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"F116 succession threshold gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--succession", required=True)
    parser.add_argument("--readiness-score-field", default="readiness_score")
    parser.add_argument("--min-readiness-score", type=float, default=0.8)
    parser.add_argument("--handoff-risk-field", default="handoff_risk")
    parser.add_argument("--max-handoff-risk", type=float, default=1.0)
    args = parser.parse_args()

    try:
        payload = json.loads(pathlib.Path(args.succession).read_text())
    except Exception:
        fail("invalid succession json")

    if not isinstance(payload, dict):
        fail("succession payload must be a JSON object")

    readiness = to_float(payload.get(args.readiness_score_field), args.readiness_score_field)
    if readiness < args.min_readiness_score:
        fail(f"{args.readiness_score_field}={readiness} < {args.min_readiness_score}")

    handoff_risk = to_float(payload.get(args.handoff_risk_field), args.handoff_risk_field)
    if handoff_risk > args.max_handoff_risk:
        fail(f"{args.handoff_risk_field}={handoff_risk} > {args.max_handoff_risk}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
