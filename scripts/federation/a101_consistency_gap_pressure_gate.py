#!/usr/bin/env python3
import argparse
import csv
import pathlib
import sys


def fail(message: str) -> None:
    print(f"A101 consistency gap pressure gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def to_int(value: str, field: str) -> int:
    try:
        return int(str(value).strip())
    except ValueError:
        fail(f"invalid integer in {field}: {value!r}")


def to_float(value: str, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError:
        fail(f"invalid float in {field}: {value!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--gaps-csv", required=True)
    parser.add_argument("--max-open-gaps", type=int, default=0)
    parser.add_argument("--max-pressure", type=float, default=1.0)
    parser.add_argument("--max-avg-gap-ratio", type=float, default=0.0)
    args = parser.parse_args()

    report = None
    try:
        import json

        report = json.loads(pathlib.Path(args.report).read_text())
    except Exception as exc:
        fail(f"invalid report JSON: {exc}")

    rows = list(csv.DictReader(pathlib.Path(args.gaps_csv).read_text().splitlines()))
    if not rows:
        fail("no gap rows to evaluate")

    open_gaps = 0
    ratio_sum = 0.0
    for row in rows:
        status = str(row.get("status", "")).strip().lower()
        if status in {"open", "pending", "active"}:
            open_gaps += 1
        ratio_sum += to_float(row.get("gap_ratio", "0.0"), "gap_ratio")

    avg_gap_ratio = ratio_sum / len(rows)
    pressure = float(report.get("consistency_pressure", 0.0)) if isinstance(report, dict) else 0.0

    if open_gaps > args.max_open_gaps or pressure > args.max_pressure or avg_gap_ratio > args.max_avg_gap_ratio:
        fail(f"open_gaps={open_gaps} pressure={pressure} avg_gap_ratio={avg_gap_ratio}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
