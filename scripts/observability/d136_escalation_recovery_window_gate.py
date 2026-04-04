#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E136 escalation recovery window gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E136 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E136 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E136 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E136 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E136 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E136 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E136 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E136 invalid {field} in {path}: {exc}")


def _to_int(value: object, path: pathlib.Path, field: str) -> int:
    try:
        return int(round(float(str(value).strip())))
    except ValueError as exc:
        fail(f"E136 invalid {field} in {path}: {exc}")


def _max_positive_step(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return max((max(0.0, curr - prev) for prev, curr in zip(values, values[1:])), default=0.0)


def _window_pairs(values: list[float], window_size: int) -> list[list[float]]:
    if not values:
        return []
    if window_size <= 0 or window_size > len(values):
        return [values]
    return [values[start : start + window_size] for start in range(0, len(values) - window_size + 1)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--escalations", required=True)
    parser.add_argument("--time-field", default="bucket")
    parser.add_argument("--open-field", default="open_escalations")
    parser.add_argument("--recovered-field", default="recovered_escalations")
    parser.add_argument("--recovery-window-field", default="recovery_window_hours")
    parser.add_argument("--window-size", type=int, default=3)
    parser.add_argument("--max-window-gap", type=float, default=0.0)
    parser.add_argument("--max-window-lag", type=float, default=0.0)
    parser.add_argument("--max-window-lag-regression", type=float, default=0.0)
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
        fail("E136 empty escalation data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    open_counts = [_to_int(row[args.open_field], escalations_path, args.open_field) for row in ordered]
    recovered_counts = [
        _to_int(row[args.recovered_field], escalations_path, args.recovered_field)
        for row in ordered
    ]
    windows = [
        _to_float(row[args.recovery_window_field], escalations_path, args.recovery_window_field)
        for row in ordered
    ]

    gap_values: list[float] = []
    for open_window, recovered_window in zip(
        _window_pairs([float(n) for n in open_counts], args.window_size),
        _window_pairs([float(n) for n in recovered_counts], args.window_size),
    ):
        open_sum = sum(open_window)
        recovered_sum = sum(recovered_window)
        if open_sum <= 0.0:
            gap_values.append(0.0)
        else:
            recovered_ratio = min(1.0, max(0.0, recovered_sum / open_sum))
            gap_values.append(1.0 - recovered_ratio)

    lag_values = [max(window) for window in _window_pairs(windows, args.window_size)] if windows else [0.0]

    window_gap = max(gap_values) if gap_values else 0.0
    window_lag = max(lag_values) if lag_values else 0.0
    window_lag_regression = _max_positive_step(lag_values)

    report_gap = _to_float(
        report.get("escalation_recovery_window_gap_max", 0.0),
        report_path,
        "escalation_recovery_window_gap_max",
    )
    report_lag = _to_float(
        report.get("escalation_recovery_window_lag_max", 0.0),
        report_path,
        "escalation_recovery_window_lag_max",
    )
    report_lag_regression = _to_float(
        report.get("escalation_recovery_window_lag_regression_max", 0.0),
        report_path,
        "escalation_recovery_window_lag_regression_max",
    )

    if window_gap < report_gap:
        window_gap = report_gap
    if window_lag < report_lag:
        window_lag = report_lag
    if window_lag_regression < report_lag_regression:
        window_lag_regression = report_lag_regression

    if window_gap > args.max_window_gap:
        fail(f"E136 window_gap={window_gap} > max_window_gap={args.max_window_gap}")
    if window_lag > args.max_window_lag:
        fail(f"E136 window_lag={window_lag} > max_window_lag={args.max_window_lag}")
    if window_lag_regression > args.max_window_lag_regression:
        fail(
            f"E136 window_lag_regression={window_lag_regression} > "
            f"max_window_lag_regression={args.max_window_lag_regression}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
