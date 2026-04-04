#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"F105 federation policy enabled gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _to_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        fail(f"{field} must be boolean: {value!r}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", required=True)
    parser.add_argument("--require-policy", action="store_true", default=True)
    args = parser.parse_args()

    try:
        data = json.loads(pathlib.Path(args.board).read_text())
    except Exception:
        fail("invalid board json")

    if not isinstance(data, dict):
        fail("board payload must be a JSON object")

    enabled = _to_bool(data.get("federation_policy_enabled"), "federation_policy_enabled")
    if args.require_policy and not enabled:
        fail("federation_policy_enabled is false")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
