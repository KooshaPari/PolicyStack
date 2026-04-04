#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
from typing import Any


def fail(message: str) -> None:
    print(f"E208 federation threshold window regression gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_report(path: pathlib.Path) -> list[dict[str, Any]] | dict[str, Any]:
    raw = path.read_text()
    if path.suffix.lower() == ".csv":
        return list(csv.DictReader(raw.splitlines()))
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON report {path}: {exc}")


def extract_rows(
    payload: list[dict[str, Any]] | dict[str, Any], lane_key: str
) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    rows = payload.get("items") or payload.get("records") or payload.get("entries") or payload.get(
        lane_key
    )
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def parse_float(value: object, label: str) -> float:
    try:
        return float(str(value))
    except Exception:
        fail(f"invalid float for {label}: {value!r}")


def parse_int(value: object, label: str) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        fail(f"invalid integer for {label}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold-window-regression-report", required=True)
    parser.add_argument("--max-threshold-window-regression-rate", type=float, default=0.02)
    parser.add_argument("--min-threshold-window-consistency-rate", type=float, default=0.98)
    parser.add_argument("--max-threshold-window-regression-breach-count", type=int, default=0)
    args = parser.parse_args()

    payload = load_report(pathlib.Path(args.threshold_window_regression_report))
    rows = extract_rows(payload, "federation_threshold_window_regression")

    max_threshold_window_regression_rate = 0.0
    threshold_window_consistency_rate = 1.0
    threshold_window_regression_breach_count = 0

    for row in rows:
        max_threshold_window_regression_rate = max(
            max_threshold_window_regression_rate,
            parse_float(
                row.get(
                    "threshold_window_regression_rate",
                    row.get(
                        "federation_threshold_window_regression_rate",
                        row.get("regression_rate", 0.0),
                    ),
                ),
                "threshold_window_regression_rate",
            ),
        )
        threshold_window_consistency_rate = min(
            threshold_window_consistency_rate,
            parse_float(
                row.get(
                    "threshold_window_consistency_rate",
                    row.get(
                        "federation_threshold_window_consistency_rate",
                        row.get("consistency_rate", 1.0),
                    ),
                ),
                "threshold_window_consistency_rate",
            ),
        )
        threshold_window_regression_breach_count += parse_int(
            row.get(
                "threshold_window_regression_breach_count",
                row.get("window_regression_breach_count", 0),
            ),
            "threshold_window_regression_breach_count",
        )

    if (
        max_threshold_window_regression_rate > args.max_threshold_window_regression_rate
        or threshold_window_consistency_rate < args.min_threshold_window_consistency_rate
        or threshold_window_regression_breach_count
        > args.max_threshold_window_regression_breach_count
    ):
        fail("thresholds exceeded")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
