#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"C112 playbook progress gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_int(v, field):
    try:
        return int(v)
    except (TypeError, ValueError):
        fail(f"invalid int in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playbook", required=True)
    parser.add_argument("--max-paused-steps", type=int, default=0)
    parser.add_argument("--max-stalled-workflows", type=int, default=0)
    parser.add_argument("--min-completion-pct", type=int, default=100)
    args = parser.parse_args()

    payload = json.loads(pathlib.Path(args.playbook).read_text())
    if not isinstance(payload, dict):
        fail("playbook JSON must be object")

    steps = payload.get("steps", [])
    if not isinstance(steps, list):
        fail("playbook.steps must be list")

    paused = 0
    stalled = 0
    for step in steps:
        if not isinstance(step, dict):
            continue
        state = str(step.get("state", "")).strip().lower()
        if state == "paused":
            paused += 1
        if state == "stalled":
            stalled += 1

    if paused > args.max_paused_steps:
        fail(f"paused_steps={paused}")

    if stalled > args.max_stalled_workflows:
        fail(f"stalled_workflows={stalled}")

    completion = payload.get("completion_percent")
    completion_pct = to_int(completion, "completion_percent")
    if completion_pct < args.min_completion_pct:
        fail(f"completion_percent={completion_pct}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
