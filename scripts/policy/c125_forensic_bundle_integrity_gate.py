#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E125 C125 forensic bundle integrity gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--forensics", required=True)
    parser.add_argument("--max-integrity-failures", type=int, default=0)
    parser.add_argument("--max-integrity-failure-rate", type=float, default=0.0)
    args = parser.parse_args()

    rows = load_rows(args.forensics, ("forensics", "bundles", "integrity"))
    total = 0
    failures = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        total += 1
        integrity_ok = to_bool(
            row.get(
                "integrity_ok",
                row.get("bundle_integrity_ok", row.get("checksum_match", row.get("verified", True))),
            )
        )
        if not integrity_ok:
            failures += 1

    if total == 0:
        fail("no forensic entries found")
    failure_rate = failures / total
    if args.max_integrity_failures and failures > args.max_integrity_failures:
        fail(f"integrity_failures={failures}")
    if args.max_integrity_failure_rate and failure_rate > to_float(
        args.max_integrity_failure_rate, "max_integrity_failure_rate"
    ):
        fail(f"integrity_failure_rate={failure_rate:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
