#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E120 C120 playbook guardrail stability gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y", "ok", "pass"}


def to_float(v, field: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def load_rows(path: str, keys: tuple[str, ...]) -> list[dict]:
    p = pathlib.Path(path)
    if p.suffix.lower() == ".csv":
        return list(csv.DictReader(p.read_text().splitlines()))
    payload = json.loads(p.read_text())
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            rows = payload.get(key)
            if isinstance(rows, list):
                return rows
        if payload and all(isinstance(v, dict) for v in payload.values()):
            return list(payload.values())
    fail("input must be CSV rows or JSON list/object with known keys")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playbook", required=True)
    parser.add_argument("--max-unstable-steps", type=int, default=0)
    parser.add_argument("--max-unstable-rate", type=float, default=0.0)
    args = parser.parse_args()

    rows = load_rows(args.playbook, ("steps", "playbook", "guardrails"))
    total = 0
    unstable = 0
    bad_states = {"failed", "abandoned", "flaky", "blocked"}
    for row in rows:
        if not isinstance(row, dict):
            continue
        total += 1
        state = str(row.get("state", "")).strip().lower()
        stable = to_bool(row.get("guardrail_stable", True))
        if state in bad_states or not stable:
            unstable += 1

    if total == 0:
        fail("no playbook steps found")
    unstable_rate = unstable / total
    if args.max_unstable_steps and unstable > args.max_unstable_steps:
        fail(f"unstable_steps={unstable}")
    if args.max_unstable_rate and unstable_rate > to_float(args.max_unstable_rate, "max_unstable_rate"):
        fail(f"unstable_rate={unstable_rate:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
