#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"C116 playbook guardrail gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playbook", required=True)
    parser.add_argument("--max-abandoned-steps", type=int, default=0)
    args = parser.parse_args()

    payload = json.loads(pathlib.Path(args.playbook).read_text())
    if not isinstance(payload, dict):
        fail("playbook JSON must be object")

    steps = payload.get("steps", [])
    if not isinstance(steps, list):
        fail("playbook.steps must be list")

    abandoned = 0
    for step in steps:
        if not isinstance(step, dict):
            continue
        state = str(step.get("state", "")).strip().lower()
        if state == "abandoned":
            abandoned += 1

    if args.max_abandoned_steps and abandoned > args.max_abandoned_steps:
        fail(f"abandoned_steps={abandoned}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
