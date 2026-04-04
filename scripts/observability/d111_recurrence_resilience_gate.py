#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"D111 recurrence resilience gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"D111 missing {label} file: {path}")


def _read_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"D111 invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"D111 report must be object: {path}")
    return payload


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"D111 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"D111 invalid recurrence CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        fail(f"D111 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--recurrence-csv", required=True)
    parser.add_argument("--time-field", default="window")
    parser.add_argument("--value-field", default="recurrence_rate")
    parser.add_argument("--max-rate-increase", type=float, default=0.0)
    parser.add_argument("--max-run-length", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.recurrence_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "recurrence")

    report = _read_json(report_path)
    rows = _read_csv(csv_path, {args.time_field, args.value_field})
    if not rows:
        fail("D111 recurrence resilience gate failed: empty recurrence data")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or ""))
    values = [
        _to_float(row.get(args.value_field, ""), csv_path, args.value_field)
        for row in ordered
    ]
    if len(values) < 2:
        fail("D111 recurrence resilience gate failed: insufficient recurrence points")

    increases = []
    current_run = 0
    max_run = 0
    for previous, current in zip(values, values[1:]):
        delta = current - previous
        if delta > args.max_rate_increase:
            increases.append(delta)
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 0

    max_increase = max(increases, default=0.0)
    reported_increase = float(report.get("recurrence_rate_increase_max", 0.0))
    if max_increase < reported_increase:
        max_increase = reported_increase
    reported_run = int(report.get("recurrence_increase_run", 0))
    max_run = max(max_run, reported_run)

    if max_increase > args.max_rate_increase:
        fail(f"D111 max_rate_increase={max_increase} > max_rate_increase={args.max_rate_increase}")
    if max_run > args.max_run_length:
        fail(f"D111 max_run_length={max_run} > max_run_length={args.max_run_length}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
