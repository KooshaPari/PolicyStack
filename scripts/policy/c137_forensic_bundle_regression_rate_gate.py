#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E137 C137 forensic bundle regression rate gate failed: {message}", file=sys.stderr)
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
    parser.add_argument("--allowed-regression-delta", type=float, default=0.0)
    parser.add_argument("--max-regressions", type=int, default=0)
    parser.add_argument("--max-regression-rate", type=float, default=0.0)
    args = parser.parse_args()

    rows = load_rows(args.forensics, ("forensics", "bundles", "regression"))
    total = 0
    regressions = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        total += 1
        baseline_score = to_float(
            row.get(
                "forensic_bundle_baseline_score",
                row.get("baseline_score", row.get("previous_score", 0.0)),
            ),
            "forensic_bundle_baseline_score",
        )
        current_score = to_float(
            row.get(
                "forensic_bundle_score",
                row.get("current_score", row.get("score", baseline_score)),
            ),
            "forensic_bundle_score",
        )
        explicit_regression = to_bool(
            row.get("regression", row.get("forensic_bundle_regression", False))
        )
        if explicit_regression or (baseline_score - current_score > args.allowed_regression_delta):
            regressions += 1

    if total == 0:
        fail("no forensic entries found")
    regression_rate = regressions / total
    if args.max_regressions and regressions > args.max_regressions:
        fail(f"regressions={regressions}")
    if args.max_regression_rate and regression_rate > to_float(
        args.max_regression_rate, "max_regression_rate"
    ):
        fail(f"regression_rate={regression_rate:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
