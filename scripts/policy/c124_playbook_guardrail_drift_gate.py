#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E124 C124 playbook guardrail drift gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--max-drift-steps", type=int, default=0)
    parser.add_argument("--max-drift-rate", type=float, default=0.0)
    parser.add_argument("--max-drift-score", type=float, default=0.0)
    args = parser.parse_args()

    rows = load_rows(args.playbook, ("steps", "playbook", "guardrails"))
    total = 0
    drifted = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        total += 1
        drift_flag = to_bool(row.get("guardrail_drift", row.get("is_drifted", False)))
        drift_score = to_float(row.get("drift_score", 0.0), "drift_score")
        if drift_flag or (args.max_drift_score and drift_score > args.max_drift_score):
            drifted += 1

    if total == 0:
        fail("no playbook steps found")
    drift_rate = drifted / total
    if args.max_drift_steps and drifted > args.max_drift_steps:
        fail(f"drift_steps={drifted}")
    if args.max_drift_rate and drift_rate > to_float(args.max_drift_rate, "max_drift_rate"):
        fail(f"drift_rate={drift_rate:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
