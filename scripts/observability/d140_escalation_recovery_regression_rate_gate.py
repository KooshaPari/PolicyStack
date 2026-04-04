#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E140 escalation recovery regression rate gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E140 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E140 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E140 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E140 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E140 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E140 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E140 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E140 invalid {field} in {path}: {exc}")


def _to_int(value: object, path: pathlib.Path, field: str) -> int:
    try:
        return int(round(float(str(value).strip())))
    except ValueError as exc:
        fail(f"E140 invalid {field} in {path}: {exc}")


def _max_positive_step(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return max((max(0.0, curr - prev) for prev, curr in zip(values, values[1:])), default=0.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--escalations", required=True)
    parser.add_argument("--time-field", default="bucket")
    parser.add_argument("--open-field", default="open_escalations")
    parser.add_argument("--recovered-field", default="recovered_escalations")
    parser.add_argument("--recovery-window-field", default="recovery_window_hours")
    parser.add_argument("--max-regression-rate", type=float, default=0.0)
    parser.add_argument("--max-regression-rate-step", type=float, default=0.0)
    parser.add_argument("--max-unrecovered-ratio", type=float, default=0.0)
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    escalations_path = pathlib.Path(args.escalations)
    _require_file(report_path, "report")
    _require_file(escalations_path, "escalations")

    report_rows = _read_json(report_path, "report")
    report = report_rows[0] if report_rows else {}

    rows = _load_records(
        escalations_path,
        {
            args.time_field,
            args.open_field,
            args.recovered_field,
            args.recovery_window_field,
        },
        "escalations",
    )
    if not rows:
        fail("E140 empty escalation data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    open_counts = [_to_int(row[args.open_field], escalations_path, args.open_field) for row in ordered]
    recovered_counts = [
        _to_int(row[args.recovered_field], escalations_path, args.recovered_field)
        for row in ordered
    ]
    recovery_windows = [
        _to_float(row[args.recovery_window_field], escalations_path, args.recovery_window_field)
        for row in ordered
    ]

    regression_series: list[float] = []
    unrecovered_ratios: list[float] = []
    for open_count, recovered_count, window in zip(open_counts, recovered_counts, recovery_windows):
        if open_count <= 0:
            unrecovered_ratio = 0.0
        else:
            recovered_ratio = min(1.0, max(0.0, float(recovered_count) / float(open_count)))
            unrecovered_ratio = 1.0 - recovered_ratio
        unrecovered_ratios.append(unrecovered_ratio)
        regression_series.append(unrecovered_ratio * max(0.0, window))

    regression_rate = max(regression_series) if regression_series else 0.0
    regression_rate_step = _max_positive_step(regression_series)
    unrecovered_ratio_max = max(unrecovered_ratios) if unrecovered_ratios else 0.0

    report_regression_rate = _to_float(
        report.get("escalation_recovery_regression_rate_max", 0.0),
        report_path,
        "escalation_recovery_regression_rate_max",
    )
    report_regression_rate_step = _to_float(
        report.get("escalation_recovery_regression_rate_step_max", 0.0),
        report_path,
        "escalation_recovery_regression_rate_step_max",
    )
    report_unrecovered_ratio = _to_float(
        report.get("escalation_recovery_unrecovered_ratio_max", 0.0),
        report_path,
        "escalation_recovery_unrecovered_ratio_max",
    )

    if regression_rate < report_regression_rate:
        regression_rate = report_regression_rate
    if regression_rate_step < report_regression_rate_step:
        regression_rate_step = report_regression_rate_step
    if unrecovered_ratio_max < report_unrecovered_ratio:
        unrecovered_ratio_max = report_unrecovered_ratio

    if regression_rate > args.max_regression_rate:
        fail(
            f"E140 regression_rate={regression_rate} > "
            f"max_regression_rate={args.max_regression_rate}"
        )
    if regression_rate_step > args.max_regression_rate_step:
        fail(
            f"E140 regression_rate_step={regression_rate_step} > "
            f"max_regression_rate_step={args.max_regression_rate_step}"
        )
    if unrecovered_ratio_max > args.max_unrecovered_ratio:
        fail(
            f"E140 unrecovered_ratio_max={unrecovered_ratio_max} > "
            f"max_unrecovered_ratio={args.max_unrecovered_ratio}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
