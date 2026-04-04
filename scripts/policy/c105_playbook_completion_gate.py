#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"C105 playbook completion gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_float(v, field, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        fail(f"invalid float in {field}: {v!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playbooks-json", required=True)
    parser.add_argument("--min-completion-rate", type=float, default=1.0)
    parser.add_argument("--max-failed", type=int, default=0)
    args = parser.parse_args()

    payload = json.loads(pathlib.Path(args.playbooks_json).read_text())
    if isinstance(payload, dict):
        rows = payload.get("playbooks", payload.get("items", []))
    else:
        rows = payload

    if not isinstance(rows, list):
        fail("playbooks JSON must be list or contain playbooks list")

    total = 0
    completed = 0
    failed = 0
    for item in rows:
        if not isinstance(item, dict):
            continue
        total += 1
        if str(item.get("status", "")).lower() in {"done", "completed", "success"}:
            completed += 1
        elif str(item.get("status", "")).lower() in {"failed", "error", "rejected"}:
            failed += 1

    if total == 0:
        fail("no playbook records found")

    completion_rate = to_float(completed / total, "completion_rate")
    if completion_rate < args.min_completion_rate:
        fail(f"completion_rate={completion_rate:.4f}")

    if failed > args.max_failed:
        fail(f"failed_count={failed}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
