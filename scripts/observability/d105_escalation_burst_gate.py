#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"D105 escalation burst gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"D105 missing {label} file: {path}")


def _read_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"D105 invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"D105 report must be JSON object: {path}")
    return payload


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(required - headers)
            if missing:
                fail(f"D105 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"D105 invalid escalation CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        fail(f"D105 invalid {field} in {path}: {exc}")


def _to_int(value: str, path: pathlib.Path, field: str) -> int:
    try:
        return int(round(float((value or "").strip())))
    except ValueError as exc:
        fail(f"D105 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--escalations-csv", required=True)
    parser.add_argument("--time-field", default="window_start")
    parser.add_argument("--status-field", default="status")
    parser.add_argument("--value-field", default="burst_rate")
    parser.add_argument("--burst-threshold", type=float, default=0.0)
    parser.add_argument("--max-bursts", type=int, default=0)
    parser.add_argument("--max-burst-slope", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.escalations_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "escalations")

    report = _read_json(report_path)
    rows = _read_csv(
        csv_path,
        {args.time_field, args.status_field, args.value_field},
    )
    if not rows:
        fail("D105 escalation burst gate failed: no escalation rows")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or ""))
    values = [
        _to_float(row.get(args.value_field, ""), csv_path, args.value_field)
        for row in ordered
        if (row.get(args.status_field) or "").strip().lower() in {"open", "active", "acknowledged"}
    ]
    if len(values) < 2:
        fail("D105 escalation burst gate failed: insufficient active rows")

    bursts = 0
    max_slope = 0.0
    for prior, current in zip(values, values[1:]):
        slope = current - prior
        if slope > args.burst_threshold:
            bursts += 1
            max_slope = max(max_slope, slope)

    report_bursts = _to_int(
        str(report.get("escalation_burst_count", 0)), report_path, "escalation_burst_count"
    )
    report_slope = float(report.get("escalation_burst_max_delta", 0.0))
    if report_bursts > args.max_bursts:
        fail(f"D105 burst_count={report_bursts}")
    if report_slope > max_slope:
        max_slope = report_slope

    if bursts > args.max_bursts:
        fail(f"D105 bursts={bursts} > max_bursts={args.max_bursts}")
    if max_slope > args.max_burst_slope:
        fail(f"D105 max_slope={max_slope} > max_burst_slope={args.max_burst_slope}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
