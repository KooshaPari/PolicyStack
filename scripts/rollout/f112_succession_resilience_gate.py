#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"F112 succession resilience gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _to_float(value: object, field: str) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--succession", required=True)
    parser.add_argument("--min-readiness-score", type=float, default=0.8)
    args = parser.parse_args()

    try:
        payload = json.loads(pathlib.Path(args.succession).read_text())
    except Exception:
        fail("invalid succession json")

    if not isinstance(payload, dict):
        fail("succession payload must be a JSON object")

    readiness = _to_float(payload.get("readiness_score"), "readiness_score")
    if readiness < args.min_readiness_score:
        fail(f"readiness_score={readiness}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
