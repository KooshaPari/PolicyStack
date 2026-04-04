#!/usr/bin/env python3
import argparse
import csv
import json
import pathlib
import sys


def fail(message: str) -> None:
    print(f"E128 escalation recovery stability gate failed: {message}", file=sys.stderr)
    raise SystemExit(2)


def _require_file(path: pathlib.Path, label: str) -> None:
    if not path.is_file():
        fail(f"E128 missing {label} file: {path}")


def _to_records(payload: object, path: pathlib.Path, label: str) -> list[dict]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    fail(f"E128 invalid {label} JSON shape (expected object or list[object]): {path}")
    return []


def _read_json(path: pathlib.Path, label: str) -> list[dict]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        fail(f"E128 invalid {label} JSON {path}: {exc}")
    return _to_records(payload, path, label)


def _read_csv(path: pathlib.Path, required: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                fail(f"E128 {label} CSV missing headers {missing}: {path}")
            return list(reader)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"E128 invalid {label} CSV {path}: {exc}")


def _load_records(path: pathlib.Path, required: set[str], label: str) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, required, label)
    if suffix == ".json":
        rows = _read_json(path, label)
        for idx, row in enumerate(rows):
            missing = sorted(field for field in required if field not in row)
            if missing:
                fail(f"E128 {label} JSON row {idx} missing keys {missing}: {path}")
        return rows
    fail(f"E128 unsupported {label} format (expected .csv or .json): {path}")
    return []


def _to_float(value: object, path: pathlib.Path, field: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        fail(f"E128 invalid {field} in {path}: {exc}")


def _to_int(value: object, path: pathlib.Path, field: str) -> int:
    try:
        return int(round(float(str(value).strip())))
    except ValueError as exc:
        fail(f"E128 invalid {field} in {path}: {exc}")


def _window_max_span(values: list[float], window_size: int) -> float:
    if not values:
        return 0.0
    if window_size <= 0 or window_size > len(values):
        return max(values) - min(values)
    best = 0.0
    for start in range(0, len(values) - window_size + 1):
        window = values[start : start + window_size]
        span = max(window) - min(window)
        if span > best:
            best = span
    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--escalations", required=True)
    parser.add_argument("--time-field", default="bucket")
    parser.add_argument("--open-field", default="open_escalations")
    parser.add_argument("--recovered-field", default="recovered_escalations")
    parser.add_argument("--recovery-lag-field", default="recovery_lag_hours")
    parser.add_argument("--window-size", type=int, default=3)
    parser.add_argument("--max-recovery-ratio-gap", type=float, default=0.0)
    parser.add_argument("--max-lag-window-span", type=float, default=0.0)
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
        fail("E128 empty escalation data")

    ordered = sorted(rows, key=lambda row: str(row.get(args.time_field, "")))
    open_counts = [_to_int(row[args.open_field], escalations_path, args.open_field) for row in ordered]
    recovered_counts = [
        _to_int(row[args.recovered_field], escalations_path, args.recovered_field)
        for row in ordered
    ]
    lags = [_to_float(row[args.recovery_lag_field], escalations_path, args.recovery_lag_field) for row in ordered]

    ratio_gaps: list[float] = []
    for open_n, recovered_n in zip(open_counts, recovered_counts):
        if open_n <= 0:
            ratio_gaps.append(0.0)
            continue
        recovered_ratio = min(1.0, max(0.0, float(recovered_n) / float(open_n)))
        ratio_gaps.append(1.0 - recovered_ratio)

    recovery_ratio_gap = max(ratio_gaps) if ratio_gaps else 0.0
    lag_window_span = _window_max_span(lags, args.window_size)

    report_ratio_gap = _to_float(
        report.get("escalation_recovery_ratio_gap_max", 0.0),
        report_path,
        "escalation_recovery_ratio_gap_max",
    )
    report_lag_span = _to_float(
        report.get("escalation_recovery_lag_window_span_max", 0.0),
        report_path,
        "escalation_recovery_lag_window_span_max",
    )

    if recovery_ratio_gap < report_ratio_gap:
        recovery_ratio_gap = report_ratio_gap
    if lag_window_span < report_lag_span:
        lag_window_span = report_lag_span

    if recovery_ratio_gap > args.max_recovery_ratio_gap:
        fail(
            f"E128 recovery_ratio_gap={recovery_ratio_gap} > "
            f"max_recovery_ratio_gap={args.max_recovery_ratio_gap}"
        )
    if lag_window_span > args.max_lag_window_span:
        fail(
            f"E128 lag_window_span={lag_window_span} > "
            f"max_lag_window_span={args.max_lag_window_span}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
