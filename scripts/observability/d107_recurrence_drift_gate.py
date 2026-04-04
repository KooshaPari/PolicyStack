#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"D107 recurrence drift gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"D107 missing {label} file: {path}")


def _read_json(path: pathlib.Path) -> dict:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"D107 invalid report JSON {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"D107 report must be object: {path}")
    return payload


def _read_csv(path: pathlib.Path, required: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"D107 CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"D107 invalid recurrence CSV {path}: {exc}")


def _to_float(value: str, path: pathlib.Path, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError as exc:
        fail(f"D107 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--recurrence-csv", required=True)
    parser.add_argument("--time-field", default="window")
    parser.add_argument("--value-field", default="recurrence_rate")
    parser.add_argument("--max-drift", type=float, default=0.0)
    parser.add_argument("--max-magnitude", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    csv_path = pathlib.Path(args.recurrence_csv)
    _require_file(report_path, "report")
    _require_file(csv_path, "recurrence")

    report = _read_json(report_path)
    rows = _read_csv(csv_path, {args.time_field, args.value_field})
    if not rows:
        fail("D107 recurrence drift gate failed: empty recurrence rows")

    ordered = sorted(rows, key=lambda row: (row.get(args.time_field) or ""))
    values = [_to_float(row.get(args.value_field, ""), csv_path, args.value_field) for row in ordered]
    if len(values) < 2:
        fail("D107 recurrence drift gate failed: insufficient recurrence rows")

    deltas = [curr - prev for prev, curr in zip(values, values[1:])]
    drift_points = [d for d in deltas if d > 0]
    max_magnitude = max([abs(d) for d in deltas], default=0.0)

    if max_magnitude > args.max_magnitude:
        fail(f"D107 max_magnitude={max_magnitude} > max_magnitude={args.max_magnitude}")

    report_drift = float(report.get("recurrence_drift_windows", 0.0))
    if drift_points:
        if report_drift > 0:
            drift_points = max(len(drift_points), int(report_drift))
        drift = len(drift_points)
    else:
        drift = 0
    report_drift = int(report_drift)
    drift = max(drift, report_drift)

    if drift > args.max_drift:
        fail(f"D107 drift_windows={drift} > max_drift={args.max_drift}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
