#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E124 escalation recovery budget gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E124 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E124 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E124 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E124 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E124 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E124 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E124 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E124 invalid {field} in {path}: {exc}")


def _to_int(value: object, path: pathlib.Path, field: str) -> int:
    try:
        return int(round(float(str(value).strip())))
    except ValueError as exc:
        fail(f"E124 invalid {field} in {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--escalations", required=True)
    parser.add_argument("--time-field", default="bucket")
    parser.add_argument("--open-field", default="open_escalations")
    parser.add_argument("--recovered-field", default="recovered_escalations")
    parser.add_argument("--recovery-lag-field", default="recovery_lag_hours")
    parser.add_argument("--max-open-escalations", type=int, default=0)
    parser.add_argument("--max-recovery-lag-hours", type=float, default=0.0)
    parser.add_argument("--max-unrecovered-count", type=int, default=0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    escalations_path = pathlib.Path(args.escalations)
    _require_file(report_path, "report")
    _require_file(escalations_path, "escalations")

    report_rows = _read_json(report_path, "report")
    report = report_rows[0] if report_rows else {}

    rows = _load_records(
        escalations_path,
        {args.time_field, args.open_field, args.recovered_field, args.recovery_lag_field},
        "escalations",
    )
    if not rows:
        fail("E124 empty escalation data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    open_counts = [_to_int(row[args.open_field], escalations_path, args.open_field) for row in ordered]
    recovered_counts = [
        _to_int(row[args.recovered_field], escalations_path, args.recovered_field)
        for row in ordered
    ]
    lags = [_to_float(row[args.recovery_lag_field], escalations_path, args.recovery_lag_field) for row in ordered]

    max_open = max(open_counts)
    max_lag = max(lags)
    unrecovered = sum(max(0, open_n - recovered_n) for open_n, recovered_n in zip(open_counts, recovered_counts))

    report_open = _to_int(
        report.get("escalation_open_count_max", 0),
        report_path,
        "escalation_open_count_max",
    )
    report_lag = _to_float(
        report.get("escalation_recovery_lag_hours_max", 0.0),
        report_path,
        "escalation_recovery_lag_hours_max",
    )
    report_unrecovered = _to_int(
        report.get("escalation_unrecovered_count", 0),
        report_path,
        "escalation_unrecovered_count",
    )

    if max_open < report_open:
        max_open = report_open
    if max_lag < report_lag:
        max_lag = report_lag
    if unrecovered < report_unrecovered:
        unrecovered = report_unrecovered

    if max_open > args.max_open_escalations:
        fail(
            f"E124 max_open_escalations={max_open} > "
            f"max_open_escalations={args.max_open_escalations}"
        )
    if max_lag > args.max_recovery_lag_hours:
        fail(
            f"E124 max_recovery_lag_hours={max_lag} > "
            f"max_recovery_lag_hours={args.max_recovery_lag_hours}"
        )
    if unrecovered > args.max_unrecovered_count:
        fail(
            f"E124 unrecovered_count={unrecovered} > "
            f"max_unrecovered_count={args.max_unrecovered_count}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
